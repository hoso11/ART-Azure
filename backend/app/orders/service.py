from datetime import datetime
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
    OrderStatus.completed: [],
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


async def update_order(db: AsyncSession, order_id: int, **kwargs) -> Order:
    order = await get_order_by_id(db, order_id)

    transitioned_to_production = False
    if "status" in kwargs and kwargs["status"]:
        new_status = OrderStatus(kwargs["status"])
        current_status = order.status
        if new_status not in VALID_TRANSITIONS.get(current_status, []):
            raise ValidationException(
                detail=f"Cannot transition from {current_status.value} to {new_status.value}",
                code="invalid_status_transition",
            )
        logger.info("order.status_change", order_id=order_id, old=current_status.value, new=new_status.value)
        if new_status == OrderStatus.in_production:
            transitioned_to_production = True

    for key, value in kwargs.items():
        if value is not None:
            setattr(order, key, value)

    await db.flush()

    # Side-effect: when an order enters production, seed an initial production
    # stage (cutting/pending) if none exists yet. Idempotent — re-saves are no-ops.
    if transitioned_to_production:
        from app.production.service import ensure_initial_stage
        await ensure_initial_stage(db, order_id)

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
