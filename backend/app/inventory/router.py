from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.inventory import service, schemas
from app.users.models import User

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ── Materials ───────────────────────────────────────────

@router.get("/materials", response_model=schemas.MaterialListResponse)
async def list_materials(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    materials, total = await service.list_materials(db, page, limit, sort_by, sort_order, search)
    return schemas.MaterialListResponse(
        items=[schemas.MaterialResponse.model_validate(m) for m in materials],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/materials/low-stock", response_model=list[schemas.MaterialResponse])
async def get_low_stock(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    materials = await service.get_low_stock_materials(db)
    return [schemas.MaterialResponse.model_validate(m) for m in materials]


@router.get("/materials/{material_id}", response_model=schemas.MaterialResponse)
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    material = await service.get_material_by_id(db, material_id)
    return schemas.MaterialResponse.model_validate(material)


@router.post("/materials", response_model=schemas.MaterialResponse, status_code=201)
async def create_material(
    data: schemas.MaterialCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    material = await service.create_material(db, **data.model_dump())
    return schemas.MaterialResponse.model_validate(material)


@router.patch("/materials/{material_id}", response_model=schemas.MaterialResponse)
async def update_material(
    material_id: int,
    data: schemas.MaterialUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    material = await service.update_material(db, material_id, admin_user_id=_admin.id, **data.model_dump(exclude_unset=True))
    return schemas.MaterialResponse.model_validate(material)


@router.delete("/materials/{material_id}", status_code=204)
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_material(db, material_id)


# ── Stock Movements ─────────────────────────────────────

@router.get("/movements", response_model=schemas.StockMovementListResponse)
async def list_movements(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    material_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    movements, total = await service.list_stock_movements(db, page, limit, sort_by, sort_order, material_id)
    return schemas.StockMovementListResponse(
        items=[schemas.StockMovementResponse.model_validate(m) for m in movements],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("/movements", response_model=schemas.StockMovementResponse, status_code=201)
async def create_movement(
    data: schemas.StockMovementCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    movement = await service.create_stock_movement(
        db,
        material_id=data.material_id,
        quantity_change=data.quantity_change,
        reason=data.reason,
        created_by=admin.id,
        order_id=data.order_id,
    )
    return schemas.StockMovementResponse.model_validate(movement)
