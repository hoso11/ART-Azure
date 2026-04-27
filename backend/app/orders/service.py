from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from loguru import logger

from app.orders.models import Order, OrderItem, OrderStatus
from app.exceptions import NotFoundException, ValidationException


VALID_TRANSITIONS = {
    OrderStatus.draft: [OrderStatus.confirmed, OrderStatus.cancelled],
    OrderStatus.confirmed: [OrderStatus.in_production, OrderStatus.cancelled],
    OrderStatus.in_production: [OrderStatus.completed, OrderStatus.cancelled],
    OrderStatus.completed: [OrderStatus.shipped],
    OrderStatus.shipped: [],
    OrderStatus.cancelled: [],
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


async def _fulfill_order_items(
    db: AsyncSession,
    order: Order,
    admin_user_id: int,
) -> None:
    """Stock-first order fulfillment. For each item:
    1. Use finished product stock first (locks variant rows).
    2. Compute production_quantity = ordered - fulfilled_from_stock.
    3. Validate raw materials only for production quantities.
    4. Raise before touching anything if materials are short.
    5. Deduct variant stock and raw materials atomically.
    """
    from app.products.models import ProductSizeMaterialRequirement, ProductVariant
    from app.inventory.models import Inventory, Material
    from app.inventory.service import create_stock_movement

    # Step 1 — lock variant rows and compute per-item fulfillment plan.
    variant_ids = [item.product_variant_id for item in order.items]
    variant_result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.id.in_(variant_ids))
        .with_for_update()
    )
    variant_map: dict[int, ProductVariant] = {v.id: v for v in variant_result.scalars().all()}

    # fulfillment: list of (item, locked_variant, from_stock, to_produce)
    fulfillment: list[tuple] = []
    for item in order.items:
        variant = variant_map.get(item.product_variant_id)
        if variant is None:
            raise ValidationException(
                detail=f"Product variant {item.product_variant_id} not found",
                code="variant_not_found",
            )
        from_stock = min(variant.stock_quantity, item.quantity)
        to_produce = item.quantity - from_stock
        fulfillment.append((item, variant, from_stock, to_produce))

    # Step 2 — aggregate raw material requirements for production quantities only.
    material_requirements: dict[int, Decimal] = {}
    for item, variant, from_stock, to_produce in fulfillment:
        if to_produce == 0:
            continue  # fully fulfilled from finished stock — no raw materials needed

        req_result = await db.execute(
            select(ProductSizeMaterialRequirement).where(
                ProductSizeMaterialRequirement.product_id == variant.product_id,
                ProductSizeMaterialRequirement.size == variant.size,
            )
        )
        requirements = req_result.scalars().all()

        if not requirements:
            raise ValidationException(
                detail=(
                    f"No material requirements defined for product ID {variant.product_id} "
                    f"size '{variant.size}'. Define requirements before confirming."
                ),
                code="no_material_requirements",
            )

        for req in requirements:
            needed = req.quantity_per_item * to_produce  # only for the production portion
            material_requirements[req.material_id] = (
                material_requirements.get(req.material_id, Decimal("0")) + needed
            )

    # Step 3 — lock inventory rows and validate availability before touching anything.
    if material_requirements:
        inv_result = await db.execute(
            select(Inventory)
            .where(Inventory.material_id.in_(list(material_requirements.keys())))
            .with_for_update()
        )
        inventory_map: dict[int, Inventory] = {
            inv.material_id: inv for inv in inv_result.scalars().all()
        }

        shortages: list[tuple[int, Decimal, Decimal]] = []
        for material_id, required in material_requirements.items():
            inv = inventory_map.get(material_id)
            available = inv.quantity_on_hand if inv else Decimal("0")
            if available < required:
                shortages.append((material_id, required, available))

        if shortages:
            mat_result = await db.execute(
                select(Material).where(Material.id.in_([s[0] for s in shortages]))
            )
            mat_map = {m.id: m for m in mat_result.scalars().all()}
            lines = []
            for material_id, required, available in shortages:
                mat = mat_map.get(material_id)
                name = mat.name if mat else f"Material #{material_id}"
                unit = mat.unit if mat else ""
                lines.append(
                    f"• {name}: required {required} {unit}, available {available} {unit}, "
                    f"missing {required - available} {unit}"
                )
            raise ValidationException(
                detail="Insufficient materials:\n" + "\n".join(lines),
                code="insufficient_materials",
            )

    # Step 4 — all checks passed; deduct atomically.
    for item, variant, from_stock, to_produce in fulfillment:
        variant.stock_quantity -= from_stock
        item.fulfilled_from_stock = from_stock
        item.production_quantity = to_produce

    for material_id, required in material_requirements.items():
        await create_stock_movement(
            db,
            material_id,
            -required,
            "production_usage",
            admin_user_id,
            order_id=order.id,
        )

    order.materials_deducted = True
    await db.flush()


async def update_order(db: AsyncSession, order_id: int, admin_user_id: int | None = None, **kwargs) -> Order:
    order = await get_order_by_id(db, order_id)

    transitioned_to_production = False
    transitioned_to_confirmed = False

    if "status" in kwargs and kwargs["status"]:
        try:
            new_status = OrderStatus(kwargs["status"])
        except ValueError:
            raise ValidationException(
                detail=f"Invalid status: {kwargs['status']}",
                code="invalid_status",
            )
        current_status = order.status
        if new_status not in VALID_TRANSITIONS.get(current_status, []):
            raise ValidationException(
                detail=f"Cannot transition from {current_status.value} to {new_status.value}",
                code="invalid_status_transition",
            )
        logger.info("order.status_change", order_id=order_id, old=current_status.value, new=new_status.value)
        if new_status == OrderStatus.in_production:
            transitioned_to_production = True
        if new_status == OrderStatus.confirmed:
            transitioned_to_confirmed = True

    for key, value in kwargs.items():
        if value is not None:
            setattr(order, key, value)

    await db.flush()

    # Side-effect: when an order enters production, seed an initial production
    # stage (cutting/pending) if none exists yet. Idempotent — re-saves are no-ops.
    if transitioned_to_production:
        from app.production.service import ensure_initial_stage
        await ensure_initial_stage(db, order_id)

    # Side-effect: draft → confirmed validates and deducts inventory materials.
    # The entire block runs inside the same DB transaction; a ValidationException
    # here triggers a rollback so the status change is also reverted.
    if transitioned_to_confirmed and not order.materials_deducted:
        if admin_user_id is None:
            raise ValidationException(
                detail="Admin user ID required for material deduction on confirm",
                code="admin_required",
            )
        await _fulfill_order_items(db, order, admin_user_id)

    await db.refresh(order)
    return order


async def delete_order(db: AsyncSession, order_id: int) -> None:
    from app.production.models import ProductionStage

    order = await get_order_by_id(db, order_id)

    stage_count = await db.execute(
        select(func.count()).select_from(ProductionStage).where(ProductionStage.order_id == order_id)
    )
    if stage_count.scalar() > 0:
        raise ValidationException(
            detail="Cannot delete an order that has production stages. Cancel it instead.",
            code="order_has_production_stages",
        )

    logger.info("order.deleted", order_id=order_id, status=order.status.value)
    await db.delete(order)
    await db.flush()


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
