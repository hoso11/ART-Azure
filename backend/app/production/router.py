from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.production import service, schemas
from app.users.models import User
from app.activity import service as activity_service

router = APIRouter(prefix="/production", tags=["Production"])


@router.get("", response_model=schemas.ProductionStageListResponse)
async def list_stages(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("id"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    order_id: int | None = Query(None),
    status: str | None = Query(None),
    active: bool = Query(False),
    one_per_order: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if one_per_order:
        # Aggregated view: one row per order, picked deterministically by
        # service.compute_current. Status filter applies to the COMPUTED
        # current status. order_id/sort_by are ignored in this mode.
        stages, total = await service.list_one_per_order(
            db, page=page, limit=limit, sort_order=sort_order,
            status=status, active_only=active,
        )
    else:
        stages, total = await service.list_stages(
            db, page, limit, sort_by, sort_order, order_id, status, active_only=active
        )
    return schemas.ProductionStageListResponse(
        items=[schemas.ProductionStageResponse.model_validate(s) for s in stages],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/summary")
async def get_production_summary(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return await service.get_production_summary(db)


# ── Stock-based production batches ───────────────────────
# These routes MUST be registered before /{stage_id} so the path matcher
# does not try to parse "batches" as an integer stage id.

@router.post(
    "/batches",
    response_model=schemas.ProductionBatchResponse,
    status_code=201,
)
async def create_production_batch(
    data: schemas.ProductionBatchCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    batch = await service.create_production_batch(
        db,
        product_id=data.product_id,
        variant_id=data.variant_id,
        quantity_to_produce=data.quantity_to_produce,
        created_by=admin.id,
    )
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="production.batch_created", entity_type="production_batch", entity_id=batch.id,
        new_values={
            "product_id": batch.product_id,
            "variant_id": batch.variant_id,
            "quantity_to_produce": batch.quantity_to_produce,
            "current_stage": batch.current_stage,
            "stage_status": batch.stage_status,
            "materials_deducted": batch.materials_deducted,
        },
    )
    return schemas.ProductionBatchResponse.model_validate(batch)


@router.get("/batches", response_model=schemas.ProductionBatchListResponse)
async def list_production_batches(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    stage_status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    batches, total = await service.list_production_batches(
        db, page=page, limit=limit, stage_status=stage_status
    )
    return schemas.ProductionBatchListResponse(
        items=[schemas.ProductionBatchResponse.model_validate(b) for b in batches],
        total=total,
        page=page,
        limit=limit,
    )


@router.patch(
    "/batches/{batch_id}",
    response_model=schemas.ProductionBatchResponse,
)
async def update_production_batch(
    batch_id: int,
    data: schemas.ProductionBatchUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = await service.get_production_batch_by_id(db, batch_id)
    old = {"current_stage": existing.current_stage, "stage_status": existing.stage_status}
    batch = await service.update_production_batch(
        db,
        batch_id,
        new_stage=data.current_stage,
        new_status=data.stage_status,
    )
    new = {"current_stage": batch.current_stage, "stage_status": batch.stage_status}
    if old != new:
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="production.batch_updated", entity_type="production_batch", entity_id=batch.id,
            old_values=old, new_values=new,
        )
    return schemas.ProductionBatchResponse.model_validate(batch)


@router.patch(
    "/batches/{batch_id}/complete",
    response_model=schemas.ProductionBatchResponse,
)
async def complete_production_batch(
    batch_id: int,
    data: schemas.BatchCompleteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Apply a partial-progress delta to a stock-based batch.

    Body: {good_quantity, damaged_quantity, defect_reason?}.

    The two quantities are DELTAS (units to add now), not final totals.
    Cumulative counters live on the batch row and accumulate across calls
    until cumulative good + damaged == quantity_to_produce, at which point
    the batch flips to completed.

    Each non-final delta emits a `production.batch_progress` audit row;
    the delta that fills the batch emits `production.batch_completed`.
    A request submitted after the batch is already completed is a silent
    no-op with no audit row.
    """
    batch, changed, completed, delta_good, delta_damaged = await service.complete_production_batch(
        db, batch_id,
        good_quantity=data.good_quantity,
        damaged_quantity=data.damaged_quantity,
        defect_reason=data.defect_reason,
    )
    if changed:
        remaining_after = batch.quantity_to_produce - batch.good_quantity - batch.damaged_quantity
        if completed:
            action = "production.batch_completed"
            details = (
                f"Completed batch #{batch.id}: "
                f"+{delta_good} good, +{delta_damaged} Խոտան "
                f"to variant #{batch.variant_id} "
                f"(cumulative {batch.good_quantity}/{batch.damaged_quantity})"
            )
        else:
            action = "production.batch_progress"
            details = (
                f"Progress batch #{batch.id}: "
                f"+{delta_good} good, +{delta_damaged} Խոտան "
                f"(cumulative {batch.good_quantity}/{batch.damaged_quantity}, "
                f"մնացած {remaining_after})"
            )
        if delta_damaged > 0 and batch.defect_reason:
            details += f" — {batch.defect_reason}"
        await activity_service.log_activity(
            db, user=admin, request=request,
            action=action,
            entity_type="production_batch",
            entity_id=batch.id,
            new_values={
                "delta_good": delta_good,
                "delta_damaged": delta_damaged,
                "cumulative_good": batch.good_quantity,
                "cumulative_damaged": batch.damaged_quantity,
                "remaining": remaining_after,
                "variant_id": batch.variant_id,
                "stock_added": batch.stock_added,
            },
            details=details,
        )
    return schemas.ProductionBatchResponse.model_validate(batch)


# ── Order-based ProductionStage endpoints ────────────────

@router.post(
    "/orders/{order_id}/stages",
    response_model=list[schemas.ProductionStageResponse],
    status_code=201,
)
async def create_stages_for_order(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Seed the five default stages for an order. Idempotent."""
    stages = await service.create_stages_for_order(db, order_id)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="production.stages_created",
        entity_type="production_stage",
        entity_id=order_id,
        new_values={"order_id": order_id, "stage_count": len(stages)},
    )
    return [schemas.ProductionStageResponse.model_validate(s) for s in stages]


@router.get("/{stage_id}", response_model=schemas.ProductionStageResponse)
async def get_stage(
    stage_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stage = await service.get_stage_by_id(db, stage_id)
    return schemas.ProductionStageResponse.model_validate(stage)


@router.patch("/{stage_id}", response_model=schemas.ProductionStageResponse)
async def update_stage(
    stage_id: int,
    data: schemas.ProductionStageUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = await service.get_stage_by_id(db, stage_id)
    old_stage = existing.stage_name
    stage = await service.update_stage(db, stage_id, new_stage_name=data.stage_name)
    if old_stage != stage.stage_name:
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="production.stage_updated",
            entity_type="production_stage",
            entity_id=stage.id,
            old_values={"stage_name": old_stage.value},
            new_values={"stage_name": stage.stage_name.value},
        )
    return schemas.ProductionStageResponse.model_validate(stage)


@router.put("/{stage_id}/stage-status", response_model=schemas.ProductionStageResponse)
async def update_stage_status(
    stage_id: int,
    data: schemas.StageStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = await service.get_stage_by_id(db, stage_id)
    old_status = existing.status
    stage = await service.update_stage_status(
        db, stage_id, new_status=data.status, changed_by=admin.id, note=data.note,
    )
    if old_status != stage.status:
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="production.stage_status_changed",
            entity_type="production_stage",
            entity_id=stage.id,
            old_values={"status": old_status.value},
            new_values={"status": stage.status.value},
            details=data.note,
        )
    return schemas.ProductionStageResponse.model_validate(stage)


# ── One-row-per-order admin control ──────────────────────

@router.patch(
    "/orders/{order_id}/current",
    response_model=schemas.ProductionStageResponse,
)
async def set_order_current(
    order_id: int,
    data: schemas.OrderCurrentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Set the displayed (current_stage, current_status) for an order. May
    update multiple ProductionStage rows under the hood (to keep at most one
    in_progress) but emits a single ActivityLog entry."""
    chosen, old_stage, old_status, new_stage, new_status = await service.set_order_current(
        db, order_id,
        new_stage=data.current_stage, new_status=data.current_status,
        changed_by=admin.id, note=data.note,
    )
    if (old_stage, old_status) != (new_stage, new_status):
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="production.order_current_changed",
            entity_type="production_stage",
            entity_id=order_id,
            old_values={
                "current_stage": old_stage.value,
                "current_status": old_status.value,
            },
            new_values={
                "current_stage": new_stage.value,
                "current_status": new_status.value,
            },
            details=data.note,
        )
    return schemas.ProductionStageResponse.model_validate(chosen)
