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


# Order-based stage workflow: five stages, sequential, both directions allowed
# only between adjacent stages.
DEFAULT_STAGES: list[StageName] = [
    StageName.cutting,
    StageName.sewing,
    StageName.quality_control,
    StageName.packaging,
    StageName.ready_for_shipment,
]

VALID_STAGE_TRANSITIONS: dict[StageName, list[StageName]] = {
    StageName.cutting: [StageName.sewing],
    StageName.sewing: [StageName.cutting, StageName.quality_control],
    StageName.quality_control: [StageName.sewing, StageName.packaging],
    StageName.packaging: [StageName.quality_control, StageName.ready_for_shipment],
    StageName.ready_for_shipment: [StageName.packaging],
}


async def create_stages_for_order(db: AsyncSession, order_id: int) -> list[ProductionStage]:
    """Seed the five default ProductionStage rows for an order. Idempotent —
    if any stages already exist for this order, returns the existing rows
    unchanged.
    """
    existing_result = await db.execute(
        select(ProductionStage).where(ProductionStage.order_id == order_id)
    )
    existing = existing_result.scalars().all()
    if existing:
        return list(existing)

    stages = [
        ProductionStage(order_id=order_id, stage_name=name, status=StageStatus.pending)
        for name in DEFAULT_STAGES
    ]
    db.add_all(stages)
    await db.flush()
    for s in stages:
        await db.refresh(s)
    logger.info("production.stages_created", order_id=order_id, count=len(stages))
    return stages


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


async def update_stage(
    db: AsyncSession,
    stage_id: int,
    *,
    new_stage_name: StageName,
) -> ProductionStage:
    """Move a stage forward/backward to an adjacent stage_name."""
    stage = await get_stage_by_id(db, stage_id)
    current = stage.stage_name
    allowed = VALID_STAGE_TRANSITIONS.get(current, [])
    if new_stage_name not in allowed:
        raise ValidationException(
            detail=(
                f"Անթույլատրելի անցում՝ '{current.value}' -> '{new_stage_name.value}'. "
                f"Թույլատրելի՝ {[s.value for s in allowed]}"
            ),
            code="invalid_stage_transition",
        )
    stage.stage_name = new_stage_name
    await db.flush()
    await db.refresh(stage)
    logger.info(
        "production.stage_updated",
        stage_id=stage_id, old=current.value, new=new_stage_name.value,
    )
    return stage


async def update_stage_status(
    db: AsyncSession,
    stage_id: int,
    *,
    new_status: StageStatus,
    changed_by: int,
    note: str | None = None,
) -> ProductionStage:
    """Change stage status (pending → in_progress → completed). Writes a
    ProductionLog row when the status actually changes."""
    stage = await get_stage_by_id(db, stage_id)
    previous = stage.status
    if previous == new_status:
        return stage

    log = ProductionLog(
        production_stage_id=stage.id,
        changed_by=changed_by,
        previous_status=previous,
        new_status=new_status,
        note=note,
    )
    db.add(log)

    stage.status = new_status
    if new_status == StageStatus.in_progress and not stage.started_at:
        stage.started_at = datetime.utcnow()
    if new_status == StageStatus.completed:
        stage.completed_at = datetime.utcnow()

    await db.flush()
    await db.refresh(stage)
    logger.info(
        "production.stage_status_changed",
        stage_id=stage_id, old=previous.value, new=new_status.value,
    )
    return stage


async def get_production_summary(db: AsyncSession) -> dict:
    result = await db.execute(
        select(ProductionStage.status, func.count())
        .group_by(ProductionStage.status)
    )
    return {row[0].value: row[1] for row in result.all()}


# ── One-row-per-order aggregation (read + write) ─────────
# These helpers serve the Production page's "one row per order" view.
# They DO NOT change the underlying 5-rows-per-order schema — the existing
# rows are read and selectively updated to maintain a single-in-progress
# invariant. History is preserved.

_STAGE_INDEX: dict[StageName, int] = {s: i for i, s in enumerate(DEFAULT_STAGES)}


def compute_current(rows: list[ProductionStage]) -> ProductionStage | None:
    """Pick the single row that represents the order's displayed current stage.

    Rule (deterministic, total over any state of the 5 rows):
      - The rightmost (latest in DEFAULT_STAGES order) row whose status is
        NOT pending. If none, the leftmost row (cutting). If the order has
        no rows, returns None.
    """
    if not rows:
        return None
    non_pending = [r for r in rows if r.status != StageStatus.pending]
    if non_pending:
        return max(non_pending, key=lambda r: _STAGE_INDEX.get(r.stage_name, -1))
    return min(rows, key=lambda r: _STAGE_INDEX.get(r.stage_name, len(DEFAULT_STAGES)))


async def get_stages_for_order(db: AsyncSession, order_id: int) -> list[ProductionStage]:
    result = await db.execute(
        select(ProductionStage).where(ProductionStage.order_id == order_id)
    )
    return list(result.scalars().all())


async def list_one_per_order(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 20,
    sort_order: str = "asc",
    status: str | None = None,
    active_only: bool = False,
) -> tuple[list[ProductionStage], int]:
    """Return one ProductionStage per order — the computed current row.

    `status` filter is applied to the COMPUTED current status, not raw row
    status (per UX requirement: filtering by 'in_progress' should match the
    order's displayed current).
    """
    from app.orders.models import Order, OrderStatus

    # Fetch distinct order_ids that match active/in_production filter.
    base_query = select(ProductionStage.order_id).distinct()
    if active_only:
        base_query = base_query.join(Order, Order.id == ProductionStage.order_id).where(
            Order.status == OrderStatus.in_production
        )
    base_query = base_query.order_by(
        ProductionStage.order_id.asc() if sort_order == "asc"
        else ProductionStage.order_id.desc()
    )

    all_order_ids_result = await db.execute(base_query)
    all_order_ids = [row[0] for row in all_order_ids_result.all()]

    if not all_order_ids:
        return [], 0

    # Load all stages for these orders, group, compute current.
    stages_result = await db.execute(
        select(ProductionStage).where(ProductionStage.order_id.in_(all_order_ids))
    )
    all_stages = list(stages_result.scalars().all())
    by_order: dict[int, list[ProductionStage]] = {}
    for s in all_stages:
        by_order.setdefault(s.order_id, []).append(s)

    currents: list[ProductionStage] = []
    for oid in all_order_ids:
        cur = compute_current(by_order.get(oid, []))
        if cur is not None:
            currents.append(cur)

    if status:
        currents = [c for c in currents if c.status.value == status]

    total = len(currents)
    start = (page - 1) * limit
    return currents[start:start + limit], total


async def set_order_current(
    db: AsyncSession,
    order_id: int,
    *,
    new_stage: str,
    new_status: str,
    changed_by: int,
    note: str | None = None,
) -> tuple[ProductionStage, StageName, StageStatus, StageName, StageStatus]:
    """Set the displayed current (stage, status) for an order. Maintains the
    invariant that at most one row has status=in_progress: rows for stages
    BEFORE the chosen stage become completed; the chosen row gets the chosen
    status; rows AFTER stay/become pending. No row is deleted; later rows'
    started_at/completed_at history is preserved.

    Returns: (chosen_row, old_stage, old_status, new_stage, new_status).
    The router uses old/new pairs for audit and idempotence detection.
    """
    valid_stages = {s.value for s in StageName}
    if new_stage not in valid_stages:
        raise ValidationException(
            detail=f"Անհայտ փուլ՝ '{new_stage}'. Թույլատրելի՝ {sorted(valid_stages)}",
            code="invalid_stage",
        )
    valid_statuses = {s.value for s in StageStatus}
    if new_status not in valid_statuses:
        raise ValidationException(
            detail=f"Անհայտ կարգավիճակ՝ '{new_status}'. Թույլատրելի՝ {sorted(valid_statuses)}",
            code="invalid_stage_status",
        )

    new_stage_enum = StageName(new_stage)
    new_status_enum = StageStatus(new_status)

    rows = await get_stages_for_order(db, order_id)
    if not rows:
        raise NotFoundException(
            detail=f"No production stages for order {order_id}",
            code="production_not_found",
        )

    by_stage: dict[StageName, ProductionStage] = {r.stage_name: r for r in rows}

    old_current = compute_current(rows)
    old_stage_enum = old_current.stage_name
    old_status_enum = old_current.status

    chosen_row = by_stage.get(new_stage_enum)
    if chosen_row is None:
        raise NotFoundException(
            detail=f"Stage row '{new_stage}' missing for order {order_id}",
            code="stage_row_missing",
        )

    target_idx = _STAGE_INDEX[new_stage_enum]
    now = datetime.utcnow()

    for stage_name, row in by_stage.items():
        idx = _STAGE_INDEX[stage_name]
        if idx < target_idx:
            row.status = StageStatus.completed
            if row.completed_at is None:
                row.completed_at = now
        elif idx == target_idx:
            row.status = new_status_enum
            if new_status_enum == StageStatus.in_progress and row.started_at is None:
                row.started_at = now
            if new_status_enum == StageStatus.completed and row.completed_at is None:
                row.completed_at = now
        else:
            row.status = StageStatus.pending
            # leave started_at/completed_at as-is — preserve history per spec

    # Idempotence: if the displayed current didn't change, don't write a log row.
    changed = (old_stage_enum, old_status_enum) != (new_stage_enum, new_status_enum)
    if changed:
        log = ProductionLog(
            production_stage_id=chosen_row.id,
            changed_by=changed_by,
            previous_status=old_status_enum,
            new_status=new_status_enum,
            note=note,
        )
        db.add(log)
        logger.info(
            "production.order_current_changed",
            order_id=order_id,
            old_stage=old_stage_enum.value, old_status=old_status_enum.value,
            new_stage=new_stage_enum.value, new_status=new_status_enum.value,
        )

    await db.flush()
    await db.refresh(chosen_row)
    return chosen_row, old_stage_enum, old_status_enum, new_stage_enum, new_status_enum


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
            detail="Տվյալ ապրանքը արտադրելու համար համապատասխան նյութեր սահմանված չեն։",
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


async def complete_production_batch(
    db: AsyncSession,
    batch_id: int,
    *,
    good_quantity: int,
    damaged_quantity: int,
    defect_reason: str | None = None,
) -> tuple[ProductionBatch, bool, bool, int, int]:
    """Apply a partial-progress delta to a stock-based batch.

    Each call ADDS the given good/damaged delta to the running cumulative
    counters. variant.stock_quantity (sellable) and
    variant.damaged_stock_quantity (Խոտան) move by the delta. Materials stay
    deducted; this function never refunds.

    The batch flips to stage_status='completed' / stock_added=True only when
    cumulative good + damaged equals quantity_to_produce. Until then,
    stage_status is auto-promoted from 'pending' to 'in_progress' on the
    first non-zero delta.

    Idempotent at the *terminal* state: once stock_added=True, any subsequent
    call is a silent no-op (the second tuple element is False, the third is
    True).

    Returns:
        (batch, changed, completed, delta_good_applied, delta_damaged_applied)

        changed   — True if anything moved; False on the terminal no-op path.
        completed — True if the batch is now (or already was) fully done.
        delta_*   — the deltas the caller actually contributed (0/0 on no-op).

    Raises ValidationException with codes:
        invalid_quantities       — negative delta on either side.
        empty_delta              — delta_good == delta_damaged == 0.
        delta_exceeds_remaining  — delta would push cumulative past
                                   quantity_to_produce.
    """
    from app.products.models import ProductVariant

    # Validate deltas BEFORE locking anything.
    if good_quantity < 0:
        raise ValidationException(
            detail="Լավ քանակը չի կարող բացասական լինել",
            code="invalid_quantities",
        )
    if damaged_quantity < 0:
        raise ValidationException(
            detail="Խոտանի քանակը չի կարող բացասական լինել",
            code="invalid_quantities",
        )
    if good_quantity == 0 and damaged_quantity == 0:
        raise ValidationException(
            detail="Լավ և Խոտան քանակները չեն կարող երկուսն էլ զրո լինել",
            code="empty_delta",
        )

    # Lock the batch row.
    batch_result = await db.execute(
        select(ProductionBatch).where(ProductionBatch.id == batch_id).with_for_update()
    )
    batch = batch_result.scalar_one_or_none()
    if batch is None:
        raise NotFoundException(detail=f"Production batch {batch_id} not found")

    if batch.stock_added:
        # Terminal state — silent no-op for caller idempotency. Caller skips
        # the audit log on (changed=False, completed=True).
        return batch, False, True, 0, 0

    remaining = batch.quantity_to_produce - batch.good_quantity - batch.damaged_quantity
    delta_total = good_quantity + damaged_quantity
    if delta_total > remaining:
        raise ValidationException(
            detail=(
                f"Մուտքագրված քանակը ({delta_total}) գերազանցում է "
                f"մնացածը ({remaining})"
            ),
            code="delta_exceeds_remaining",
        )

    # Lock the variant row and add both counters atomically.
    variant_result = await db.execute(
        select(ProductVariant).where(ProductVariant.id == batch.variant_id).with_for_update()
    )
    variant = variant_result.scalar_one_or_none()
    if variant is None:
        raise NotFoundException(
            detail=f"Variant {batch.variant_id} not found — cannot complete batch"
        )

    variant.stock_quantity += good_quantity
    variant.damaged_stock_quantity += damaged_quantity

    batch.good_quantity += good_quantity
    batch.damaged_quantity += damaged_quantity
    if damaged_quantity > 0 and defect_reason:
        batch.defect_reason = defect_reason

    new_total = batch.good_quantity + batch.damaged_quantity
    is_now_complete = new_total == batch.quantity_to_produce

    if is_now_complete:
        batch.stage_status = "completed"
        batch.current_stage = "ready_for_shipment"
        batch.completed_at = datetime.utcnow()
        batch.stock_added = True
    elif batch.stage_status == "pending":
        batch.stage_status = "in_progress"

    await db.flush()
    await db.refresh(batch)
    logger.info(
        "production.batch_progress" if not is_now_complete else "production.batch_completed",
        batch_id=batch.id,
        variant_id=batch.variant_id,
        delta_good=good_quantity,
        delta_damaged=damaged_quantity,
        cumulative_good=batch.good_quantity,
        cumulative_damaged=batch.damaged_quantity,
        remaining=batch.quantity_to_produce - new_total,
        new_variant_stock=variant.stock_quantity,
        new_variant_damaged_stock=variant.damaged_stock_quantity,
    )
    return batch, True, is_now_complete, good_quantity, damaged_quantity
