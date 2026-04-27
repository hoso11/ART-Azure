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
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = await service.get_production_batch_by_id(db, batch_id)
    already_done = existing.stock_added
    batch = await service.complete_production_batch(db, batch_id)
    if not already_done and batch.stock_added:
        # Only audit the actual completion — idempotent re-calls are silent.
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="production.batch_completed", entity_type="production_batch", entity_id=batch.id,
            new_values={
                "stock_added": True,
                "quantity_added_to_variant": batch.quantity_to_produce,
                "variant_id": batch.variant_id,
            },
            details=f"Completed batch #{batch.id}, +{batch.quantity_to_produce} to variant #{batch.variant_id}",
        )
    return schemas.ProductionBatchResponse.model_validate(batch)


# ── Order-based production stages (legacy / unchanged) ──

@router.get("/{stage_id}", response_model=schemas.ProductionStageResponse)
async def get_stage(
    stage_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stage = await service.get_stage_by_id(db, stage_id)
    return schemas.ProductionStageResponse.model_validate(stage)


@router.post("/orders/{order_id}/stages", response_model=list[schemas.ProductionStageResponse], status_code=201)
async def create_stages_for_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stages = await service.create_stages_for_order(db, order_id)
    return [schemas.ProductionStageResponse.model_validate(s) for s in stages]


@router.patch("/{stage_id}", response_model=schemas.ProductionStageResponse)
async def update_stage(
    stage_id: int,
    data: schemas.ProductionStageUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = await service.get_stage_by_id(db, stage_id)
    old_status = existing.status.value if hasattr(existing.status, "value") else existing.status
    stage = await service.update_stage(db, stage_id, changed_by=admin.id, **data.model_dump(exclude_unset=True))
    new_status = stage.status.value if hasattr(stage.status, "value") else stage.status
    if old_status != new_status:
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="production.stage_updated", entity_type="production_stage", entity_id=stage.id,
            old_values={"status": old_status},
            new_values={"status": new_status},
        )
    return schemas.ProductionStageResponse.model_validate(stage)


@router.put("/{stage_id}/stage-status", response_model=schemas.ProductionStageResponse)
async def set_stage_status(
    stage_id: int,
    data: schemas.StageStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = await service.get_stage_by_id(db, stage_id)
    old_status = existing.status.value if hasattr(existing.status, "value") else existing.status
    stage = await service.update_stage_status(
        db, stage_id, new_status=data.status, changed_by=admin.id, note=data.note
    )
    new_status = stage.status.value if hasattr(stage.status, "value") else stage.status
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="production.stage_status_changed", entity_type="production_stage", entity_id=stage.id,
        old_values={"status": old_status},
        new_values={"status": new_status},
        details=data.note,
    )
    return schemas.ProductionStageResponse.model_validate(stage)
