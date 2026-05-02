from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_roles, INVENTORY_MANAGER, PRODUCTION_INVENTORY_READ
from app.inventory import service, schemas
from app.users.models import User
from app.activity import service as activity_service

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _material_snapshot(m) -> dict:
    return {
        "name": m.name,
        "sku": m.sku,
        "unit": m.unit,
        "reorder_threshold": float(m.reorder_threshold) if getattr(m, "reorder_threshold", None) is not None else None,
    }


# ── Materials ───────────────────────────────────────────

@router.get("/materials", response_model=schemas.MaterialListResponse)
async def list_materials(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _viewer: User = Depends(require_roles(*PRODUCTION_INVENTORY_READ)),
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
    _viewer: User = Depends(require_roles(*PRODUCTION_INVENTORY_READ)),
):
    materials = await service.get_low_stock_materials(db)
    return [schemas.MaterialResponse.model_validate(m) for m in materials]


@router.get("/materials/{material_id}", response_model=schemas.MaterialResponse)
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    _viewer: User = Depends(require_roles(*PRODUCTION_INVENTORY_READ)),
):
    material = await service.get_material_by_id(db, material_id)
    return schemas.MaterialResponse.model_validate(material)


@router.post("/materials", response_model=schemas.MaterialResponse, status_code=201)
async def create_material(
    data: schemas.MaterialCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*INVENTORY_MANAGER)),
):
    material = await service.create_material(db, **data.model_dump())
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="material.created", entity_type="material", entity_id=material.id,
        new_values=_material_snapshot(material),
    )
    return schemas.MaterialResponse.model_validate(material)


@router.patch("/materials/{material_id}", response_model=schemas.MaterialResponse)
async def update_material(
    material_id: int,
    data: schemas.MaterialUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*INVENTORY_MANAGER)),
):
    existing = await service.get_material_by_id(db, material_id)
    old_snapshot = _material_snapshot(existing)

    material = await service.update_material(db, material_id, admin_user_id=admin.id, **data.model_dump(exclude_unset=True))
    new_snapshot = _material_snapshot(material)
    if old_snapshot != new_snapshot:
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="material.updated", entity_type="material", entity_id=material.id,
            old_values=old_snapshot, new_values=new_snapshot,
        )
    return schemas.MaterialResponse.model_validate(material)


@router.delete("/materials/{material_id}", status_code=204)
async def delete_material(
    material_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*INVENTORY_MANAGER)),
):
    existing = await service.get_material_by_id(db, material_id)
    snapshot = _material_snapshot(existing)
    await service.delete_material(db, material_id)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="material.deleted", entity_type="material", entity_id=material_id,
        old_values=snapshot,
        details=f"Deleted {snapshot['name']}",
    )


# ── Stock Movements ─────────────────────────────────────

@router.get("/movements", response_model=schemas.StockMovementListResponse)
async def list_movements(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    material_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*INVENTORY_MANAGER)),
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*INVENTORY_MANAGER)),
):
    movement = await service.create_stock_movement(
        db,
        material_id=data.material_id,
        quantity_change=data.quantity_change,
        reason=data.reason,
        created_by=admin.id,
        order_id=data.order_id,
    )
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="inventory.stock_movement", entity_type="stock_movement", entity_id=movement.id,
        new_values={
            "material_id": movement.material_id,
            "quantity_change": float(movement.quantity_change),
            "reason": movement.reason.value if hasattr(movement.reason, "value") else movement.reason,
            "order_id": movement.order_id,
        },
    )
    return schemas.StockMovementResponse.model_validate(movement)
