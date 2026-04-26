from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from loguru import logger

from app.production.models import ProductionStage, ProductionLog, StageName, StageStatus
from app.exceptions import NotFoundException, ValidationException


VALID_STAGE_TRANSITIONS = {
    StageStatus.pending: [StageStatus.in_progress],
    StageStatus.in_progress: [StageStatus.completed],
    StageStatus.completed: [],
    StageStatus.skipped: [],
}


DEFAULT_STAGES = [
    StageName.cutting,
    StageName.sewing,
    StageName.quality_control,
    StageName.packaging,
    StageName.ready_for_shipment,
]


async def create_stages_for_order(db: AsyncSession, order_id: int) -> list[ProductionStage]:
    stages = []
    for stage_name in DEFAULT_STAGES:
        stage = ProductionStage(order_id=order_id, stage_name=stage_name)
        db.add(stage)
        stages.append(stage)
    await db.flush()
    for s in stages:
        await db.refresh(s)
    return stages


async def ensure_initial_stage(db: AsyncSession, order_id: int) -> ProductionStage | None:
    """Create a single initial production stage (cutting/pending) for an order
    if and only if no production stage exists for that order yet.

    Idempotent: safe to call repeatedly. Returns the new stage, or None if a
    stage already existed.
    """
    existing = await db.execute(
        select(ProductionStage.id).where(ProductionStage.order_id == order_id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return None

    stage = ProductionStage(
        order_id=order_id,
        stage_name=StageName.cutting,
        status=StageStatus.pending,
    )
    db.add(stage)
    await db.flush()
    await db.refresh(stage)
    logger.info("production.initial_stage_created", order_id=order_id, stage_id=stage.id)
    return stage


async def list_stages(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "id",
    sort_order: str = "asc",
    order_id: int | None = None,
    status: str | None = None,
    active_only: bool = False,
) -> tuple[list[ProductionStage], int]:
    query = select(ProductionStage).options(selectinload(ProductionStage.logs))
    count_query = select(func.count()).select_from(ProductionStage)

    if active_only:
        # Active = the underlying order is currently in production.
        # Completed/cancelled/shipped orders drop off the active production list
        # automatically; their stages remain in DB for history.
        from app.orders.models import Order, OrderStatus
        query = query.join(Order, Order.id == ProductionStage.order_id).where(
            Order.status == OrderStatus.in_production
        )
        count_query = count_query.join(Order, Order.id == ProductionStage.order_id).where(
            Order.status == OrderStatus.in_production
        )

    if order_id:
        query = query.where(ProductionStage.order_id == order_id)
        count_query = count_query.where(ProductionStage.order_id == order_id)

    if status:
        query = query.where(ProductionStage.status == status)
        count_query = count_query.where(ProductionStage.status == status)

    sort_col = getattr(ProductionStage, sort_by, ProductionStage.id)
    query = query.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().unique().all()), total


async def get_stage_by_id(db: AsyncSession, stage_id: int) -> ProductionStage:
    result = await db.execute(
        select(ProductionStage)
        .options(selectinload(ProductionStage.logs))
        .where(ProductionStage.id == stage_id)
    )
    stage = result.scalar_one_or_none()
    if not stage:
        raise NotFoundException(detail=f"Production stage {stage_id} not found")
    return stage


async def update_stage(db: AsyncSession, stage_id: int, changed_by: int, **kwargs) -> ProductionStage:
    stage = await get_stage_by_id(db, stage_id)

    if "status" in kwargs and kwargs["status"]:
        new_status = kwargs["status"]
        old_status = stage.status.value

        log = ProductionLog(
            production_stage_id=stage.id,
            changed_by=changed_by,
            previous_status=old_status,
            new_status=new_status,
            note=kwargs.get("notes"),
        )
        db.add(log)

        if new_status == StageStatus.in_progress.value and not stage.started_at:
            stage.started_at = datetime.utcnow()
        elif new_status == StageStatus.completed.value:
            stage.completed_at = datetime.utcnow()

        logger.info("production.stage_update", stage_id=stage_id, old=old_status, new=new_status)

    for key, value in kwargs.items():
        if value is not None:
            setattr(stage, key, value)

    await db.flush()
    await db.refresh(stage)
    return stage


async def update_stage_status(
    db: AsyncSession, stage_id: int, new_status: str, changed_by: int, note: str | None = None
) -> ProductionStage:
    """Change a production stage status with linear transition guard.
    Allowed: pending -> in_progress -> completed. Same-status no-op is rejected
    so callers don't double-create log rows by accident.
    """
    stage = await get_stage_by_id(db, stage_id)
    try:
        target = StageStatus(new_status)
    except ValueError:
        raise ValidationException(detail=f"Unknown stage status: {new_status}", code="invalid_stage_status")

    if target == stage.status:
        raise ValidationException(detail="Stage is already in this status", code="no_op_status")

    allowed = VALID_STAGE_TRANSITIONS.get(stage.status, [])
    if target not in allowed:
        raise ValidationException(
            detail=f"Cannot transition stage from {stage.status.value} to {target.value}",
            code="invalid_stage_transition",
        )

    # Reuse the main update path so logging + started_at/completed_at stay in one place.
    return await update_stage(db, stage_id, changed_by=changed_by, status=target.value, notes=note)


async def get_production_summary(db: AsyncSession) -> dict:
    result = await db.execute(
        select(ProductionStage.status, func.count())
        .group_by(ProductionStage.status)
    )
    return {row[0].value: row[1] for row in result.all()}
