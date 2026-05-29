from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from loguru import logger

from app.orders.models import Order, OrderItem, OrderStatus
from app.exceptions import NotFoundException, ValidationException


# Three active statuses. Admin can move freely between any two of these.
# Old enum values (in_production, shipped, cancelled) remain in the Postgres
# enum and the Python OrderStatus class so historical rows stay readable,
# but they are not valid as a *target* of any new transition. Historical
# orders stuck at a deprecated status can still be rescued by changing them
# into one of the allowed statuses (source is unrestricted; only the target
# is gated).
ALLOWED_STATUSES: set[OrderStatus] = {
    OrderStatus.draft,
    OrderStatus.confirmed,
    OrderStatus.completed,
}


async def list_orders(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    search: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    filter: str | None = None,
) -> tuple[list[Order], int]:
    query = select(Order).options(selectinload(Order.items), selectinload(Order.customer))
    count_query = select(func.count()).select_from(Order)

    if status:
        query = query.where(Order.status == status)
        count_query = count_query.where(Order.status == status)

    if filter == "active":
        # Active = not yet completed and not in any terminal/deprecated state.
        active_statuses = [OrderStatus.confirmed, OrderStatus.in_production]
        query = query.where(Order.status.in_(active_statuses))
        count_query = count_query.where(Order.status.in_(active_statuses))
    elif filter == "delayed":
        now = datetime.utcnow()
        excluded = [OrderStatus.completed, OrderStatus.cancelled]
        query = query.where(Order.deadline < now, Order.status.not_in(excluded))
        count_query = count_query.where(Order.deadline < now, Order.status.not_in(excluded))

    if customer_id:
        query = query.where(Order.customer_id == customer_id)
        count_query = count_query.where(Order.customer_id == customer_id)

    if search:
        query = query.where(Order.notes.ilike(f"%{search}%"))
        count_query = count_query.where(Order.notes.ilike(f"%{search}%"))

    sort_col = getattr(Order, sort_by, Order.created_at)
    query = query.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().unique().all()), total


async def get_order_by_id(db: AsyncSession, order_id: int) -> Order:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product_variant))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundException(detail=f"Order {order_id} not found")
    return order


async def create_order(db: AsyncSession, customer_id: int, created_by: int, items: list, **kwargs) -> Order:
    order = Order(customer_id=customer_id, created_by=created_by, **kwargs)
    db.add(order)
    await db.flush()

    for item_data in items:
        item = OrderItem(order_id=order.id, **item_data)
        db.add(item)

    await db.flush()
    await db.refresh(order)
    return await get_order_by_id(db, order.id)


async def _deduct_stock_on_completion(
    db: AsyncSession,
    order: Order,
    admin_user_id: int,
) -> None:
    """Deduct ProductVariant.stock_quantity for every order item.

    Called at most once per order, when the order transitions to status
    `completed`. Idempotency is enforced by the caller via the
    `order.stock_deducted` flag.

    Pre-flight check is all-or-nothing: if any item is short, raises
    ValidationException(code='insufficient_stock') with a per-item shortage
    list and no stock change is committed (the surrounding transaction
    rolls back together with the status change).

    Locks the variant rows with SELECT ... FOR UPDATE so two concurrent
    completions of two orders that share a variant cannot over-deduct.

    `damaged_stock_quantity` is never read or written by this function —
    only sellable `stock_quantity` participates in availability checks.
    """
    from app.products.models import ProductVariant

    if not order.items:
        order.stock_deducted = True
        await db.flush()
        return

    variant_ids = [item.product_variant_id for item in order.items]
    result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.id.in_(variant_ids))
        .with_for_update()
    )
    variant_map: dict[int, ProductVariant] = {v.id: v for v in result.scalars().all()}

    shortages: list[dict] = []
    for item in order.items:
        variant = variant_map.get(item.product_variant_id)
        if variant is None:
            raise ValidationException(
                detail=f"Product variant {item.product_variant_id} not found",
                code="variant_not_found",
            )
        if variant.stock_quantity < item.quantity:
            shortages.append({
                "product_variant_id": item.product_variant_id,
                "size": variant.size,
                "color": variant.color,
                "required": item.quantity,
                "available": variant.stock_quantity,
                "missing": item.quantity - variant.stock_quantity,
            })

    if shortages:
        lines = [
            f"• {s['size']}/{s['color']}: required {s['required']}, "
            f"available {s['available']}, missing {s['missing']}"
            for s in shortages
        ]
        raise ValidationException(
            detail="Insufficient stock:\n" + "\n".join(lines),
            code="insufficient_stock",
        )

    for item in order.items:
        variant = variant_map[item.product_variant_id]
        variant.stock_quantity -= item.quantity

    order.stock_deducted = True
    logger.info(
        "order.stock_deducted",
        order_id=order.id,
        admin_user_id=admin_user_id,
        item_count=len(order.items),
    )
    await db.flush()


async def update_order(db: AsyncSession, order_id: int, admin_user_id: int | None = None, **kwargs) -> Order:
    order = await get_order_by_id(db, order_id)

    transitioned_to_completed = False

    if "status" in kwargs and kwargs["status"]:
        try:
            new_status = OrderStatus(kwargs["status"])
        except ValueError:
            raise ValidationException(
                detail=f"Invalid status: {kwargs['status']}",
                code="invalid_status",
            )

        # Target must be one of the three allowed active statuses.
        # The source is unrestricted: orders stuck at a deprecated status
        # (in_production, shipped, cancelled) can still be rescued into the
        # allowed set.
        if new_status not in ALLOWED_STATUSES:
            raise ValidationException(
                detail=(
                    f"Status '{new_status.value}' is no longer available. "
                    f"Allowed: draft, confirmed, completed."
                ),
                code="status_not_allowed",
            )

        current_status = order.status
        if new_status == current_status:
            # Same-status patch: no-op. Don't write the field, don't trigger
            # the side-effect, don't emit an audit row from the caller.
            kwargs.pop("status")
        else:
            logger.info(
                "order.status_change",
                order_id=order_id,
                old=current_status.value,
                new=new_status.value,
            )
            if new_status == OrderStatus.completed:
                transitioned_to_completed = True

    for key, value in kwargs.items():
        if value is not None:
            setattr(order, key, value)

    await db.flush()

    # Side-effect: completion deducts finished stock once per order.
    # Idempotent via order.stock_deducted: a second `-> completed` transition
    # (e.g. completed -> draft -> completed) is a no-op.
    if transitioned_to_completed and not order.stock_deducted:
        if admin_user_id is None:
            raise ValidationException(
                detail="Admin user ID required for stock deduction on completion",
                code="admin_required",
            )
        await _deduct_stock_on_completion(db, order, admin_user_id)

    await db.refresh(order)
    return order


async def delete_order(db: AsyncSession, order_id: int) -> int:
    """Hard-delete an order. Returns the number of pending ProductionStage
    rows removed alongside it (0 if none).

    Guards (in evaluation order):
      1. order.stock_deducted == True
            -> 422 order_stock_already_deducted
      2. Any ProductionStage row for this order has status != pending
            -> 422 order_has_active_production

    When both guards pass, pending ProductionStage rows (if any) are deleted
    per-row so the ORM cascade clears production_logs on SQLite + Postgres.
    OrderItem rows cascade via Order.items' cascade="all, delete-orphan".

    ProductionBatch is intentionally NOT checked: it has no order_id (it is
    stock-replenishment, not order-fulfillment). Checking via shared variant
    ids would block unrelated orders and is a false-positive trap.
    """
    from app.production.models import ProductionStage, StageStatus

    order = await get_order_by_id(db, order_id)

    if order.stock_deducted:
        raise ValidationException(
            detail="Cannot delete an order after stock has been deducted. Cancel it instead.",
            code="order_stock_already_deducted",
        )

    stage_result = await db.execute(
        select(ProductionStage)
        .where(ProductionStage.order_id == order_id)
        .with_for_update()
    )
    stages = list(stage_result.scalars().all())
    if any(s.status != StageStatus.pending for s in stages):
        raise ValidationException(
            detail="Cannot delete an order after production has started. Cancel it instead.",
            code="order_has_active_production",
        )

    removed = 0
    for stage in stages:
        await db.delete(stage)
        removed += 1

    logger.info(
        "order.deleted",
        order_id=order_id,
        status=order.status.value,
        stages_removed=removed,
    )
    await db.delete(order)
    await db.flush()
    return removed


async def add_order_item(db: AsyncSession, order_id: int, **kwargs) -> OrderItem:
    await get_order_by_id(db, order_id)
    item = OrderItem(order_id=order_id, **kwargs)
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def delete_order_item(db: AsyncSession, item_id: int) -> None:
    result = await db.execute(select(OrderItem).where(OrderItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundException(detail=f"OrderItem {item_id} not found")
    await db.delete(item)
    await db.flush()


async def get_order_stats(db: AsyncSession) -> dict:
    total = await db.execute(select(func.count()).select_from(Order))
    active = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.status.in_([OrderStatus.confirmed, OrderStatus.in_production])
        )
    )
    from datetime import datetime
    delayed = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.deadline < datetime.utcnow(),
            Order.status.not_in([OrderStatus.shipped, OrderStatus.cancelled, OrderStatus.completed]),
        )
    )
    return {
        "total": total.scalar(),
        "active": active.scalar(),
        "delayed": delayed.scalar(),
    }
