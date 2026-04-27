from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from loguru import logger

from app.production.models import (
    ProductionStage, ProductionLog, StageName, StageStatus,
    ProductionBatch, VALID_BATCH_STAGES, VALID_BATCH_STATUSES,
)
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


# ── Stock-based production batch service ─────────────────

async def create_production_batch(
    db: AsyncSession,
    *,
    product_id: int,
    variant_id: int,
    quantity_to_produce: int,
    created_by: int,
) -> ProductionBatch:
    """Validate variant + materials, deduct raw materials, create the batch.
    All in one DB transaction — a ValidationException rolls everything back.
    """
    from decimal import Decimal
    from app.products.models import ProductVariant, ProductSizeMaterialRequirement
    from app.inventory.models import Inventory, Material
    from app.inventory.service import create_stock_movement

    if quantity_to_produce <= 0:
        raise ValidationException(
            detail="Քանակը պետք է լինի 1 կամ ավելի",
            code="invalid_quantity",
        )

    # Lock the variant row and verify it belongs to the product.
    variant_result = await db.execute(
        select(ProductVariant)
        .where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
        .with_for_update()
    )
    variant = variant_result.scalar_one_or_none()
    if variant is None:
        raise ValidationException(
            detail=f"Տարբերակ {variant_id} չի պատկանում ապրանքին {product_id}",
            code="variant_not_found",
        )

    # Look up size-keyed material requirements for this product.
    req_result = await db.execute(
        select(ProductSizeMaterialRequirement).where(
            ProductSizeMaterialRequirement.product_id == product_id,
            ProductSizeMaterialRequirement.size == variant.size,
        )
    )
    requirements = req_result.scalars().all()
    if not requirements:
        raise ValidationException(
            detail=(
                f"Նյութերի պահանջներ սահմանված չեն ապրանքի #{product_id} "
                f"չափսի «{variant.size}» համար։ Սահմանեք պահանջները նախքան արտադրությունը։"
            ),
            code="no_material_requirements",
        )

    # Aggregate required quantities per material.
    material_requirements: dict[int, Decimal] = {}
    for req in requirements:
        needed = req.quantity_per_item * Decimal(str(quantity_to_produce))
        material_requirements[req.material_id] = (
            material_requirements.get(req.material_id, Decimal("0")) + needed
        )

    # Lock inventory rows and validate availability before any mutation.
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
                f"• {name}: պետք է {required} {unit}, առկա է {available} {unit}, "
                f"պակասում է {required - available} {unit}"
            )
        raise ValidationException(
            detail="Անբավարար նյութեր:\n" + "\n".join(lines),
            code="insufficient_materials",
        )

    # All checks passed — deduct materials.
    for material_id, required in material_requirements.items():
        await create_stock_movement(
            db,
            material_id,
            -required,
            "stock_based_production",
            created_by,
        )

    batch = ProductionBatch(
        product_id=product_id,
        variant_id=variant_id,
        quantity_to_produce=quantity_to_produce,
        production_type="stock_based",
        current_stage="cutting",
        stage_status="pending",
        materials_deducted=True,
        stock_added=False,
        created_by=created_by,
    )
    db.add(batch)
    await db.flush()
    await db.refresh(batch)
    logger.info(
        "production.batch_created",
        batch_id=batch.id,
        product_id=product_id,
        variant_id=variant_id,
        quantity=quantity_to_produce,
    )
    return batch


async def list_production_batches(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    stage_status: str | None = None,
) -> tuple[list[ProductionBatch], int]:
    query = select(ProductionBatch)
    count_query = select(func.count()).select_from(ProductionBatch)

    if stage_status:
        query = query.where(ProductionBatch.stage_status == stage_status)
        count_query = count_query.where(ProductionBatch.stage_status == stage_status)

    query = query.order_by(ProductionBatch.created_at.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().unique().all()), total


async def get_production_batch_by_id(db: AsyncSession, batch_id: int) -> ProductionBatch:
    result = await db.execute(
        select(ProductionBatch).where(ProductionBatch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise NotFoundException(detail=f"Production batch {batch_id} not found")
    return batch


async def update_production_batch(
    db: AsyncSession,
    batch_id: int,
    *,
    new_stage: str | None = None,
    new_status: str | None = None,
) -> ProductionBatch:
    """Update stage and/or intermediate status. Marking a batch as `completed`
    must go through complete_production_batch() because it has the side effect
    of incrementing finished stock."""
    if new_stage is not None and new_stage not in VALID_BATCH_STAGES:
        raise ValidationException(
            detail=f"Անհայտ փուլ՝ '{new_stage}'. Թույլատրելի՝ {sorted(VALID_BATCH_STAGES)}",
            code="invalid_batch_stage",
        )
    if new_status is not None and new_status not in VALID_BATCH_STATUSES:
        raise ValidationException(
            detail=f"Անհայտ կարգավիճակ՝ '{new_status}'. Թույլատրելի՝ {sorted(VALID_BATCH_STATUSES)}",
            code="invalid_batch_status",
        )
    if new_status == "completed":
        raise ValidationException(
            detail="«Ավարտված» կարգավիճակը սահմանվում է /complete էնդփոյնթի միջոցով",
            code="use_complete_endpoint",
        )

    batch = await get_production_batch_by_id(db, batch_id)

    if batch.stage_status == "completed":
        raise ValidationException(
            detail="Ավարտված արտադրությունը չի կարող փոփոխվել",
            code="batch_already_completed",
        )

    if new_stage is not None:
        batch.current_stage = new_stage
    if new_status is not None:
        batch.stage_status = new_status

    await db.flush()
    await db.refresh(batch)
    logger.info(
        "production.batch_updated",
        batch_id=batch.id,
        stage=batch.current_stage,
        status=batch.stage_status,
    )
    return batch


async def complete_production_batch(db: AsyncSession, batch_id: int) -> ProductionBatch:
    """Mark a batch completed and add `quantity_to_produce` to variant stock.
    Idempotent: if `stock_added` is already True, the second call returns the
    batch unchanged and never re-increments stock.
    """
    from app.products.models import ProductVariant

    # Lock the batch row.
    batch_result = await db.execute(
        select(ProductionBatch).where(ProductionBatch.id == batch_id).with_for_update()
    )
    batch = batch_result.scalar_one_or_none()
    if batch is None:
        raise NotFoundException(detail=f"Production batch {batch_id} not found")

    if batch.stock_added:
        # Already completed — return unchanged. Idempotent by design.
        return batch

    # Lock the variant row and add the produced quantity to its stock.
    variant_result = await db.execute(
        select(ProductVariant).where(ProductVariant.id == batch.variant_id).with_for_update()
    )
    variant = variant_result.scalar_one_or_none()
    if variant is None:
        raise NotFoundException(
            detail=f"Variant {batch.variant_id} not found — cannot complete batch"
        )

    variant.stock_quantity += batch.quantity_to_produce
    batch.stage_status = "completed"
    batch.current_stage = "ready_for_shipment"
    batch.completed_at = datetime.utcnow()
    batch.stock_added = True

    await db.flush()
    await db.refresh(batch)
    logger.info(
        "production.batch_completed",
        batch_id=batch.id,
        variant_id=batch.variant_id,
        added=batch.quantity_to_produce,
        new_variant_stock=variant.stock_quantity,
    )
    return batch
