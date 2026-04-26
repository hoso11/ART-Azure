from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.production import service, schemas
from app.users.models import User

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
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    stage = await service.update_stage(db, stage_id, changed_by=admin.id, **data.model_dump(exclude_unset=True))
    return schemas.ProductionStageResponse.model_validate(stage)


@router.put("/{stage_id}/stage-status", response_model=schemas.ProductionStageResponse)
async def set_stage_status(
    stage_id: int,
    data: schemas.StageStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    stage = await service.update_stage_status(
        db, stage_id, new_status=data.status, changed_by=admin.id, note=data.note
    )
    return schemas.ProductionStageResponse.model_validate(stage)
