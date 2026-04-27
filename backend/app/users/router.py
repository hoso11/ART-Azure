from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.users import service, schemas
from app.users.models import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=schemas.UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    users, total = await service.list_users(db, page, limit, sort_by, sort_order, search)
    return schemas.UserListResponse(
        items=[schemas.UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{user_id}", response_model=schemas.UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = await service.get_user_by_id(db, user_id)
    return schemas.UserResponse.model_validate(user)


@router.post("", response_model=schemas.UserResponse, status_code=201)
async def create_user(
    data: schemas.UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = await service.create_user(
        db, data.email, data.password, data.role, data.customer_id, data.discount_percent
    )
    return schemas.UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=schemas.UserResponse)
async def update_user(
    user_id: int,
    data: schemas.UserUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = await service.update_user(db, user_id, **data.model_dump(exclude_unset=True))
    return schemas.UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_user(db, user_id)
