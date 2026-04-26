from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin, require_authenticated
from app.customers import service, schemas
from app.users.models import User

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/me", response_model=schemas.CustomerResponse)
async def get_my_customer(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_authenticated),
):
    """Return the customer linked to the current user's account."""
    if not current_user.customer_id:
        from app.exceptions import NotFoundException
        raise NotFoundException(detail="No customer linked to your account")
    customer = await service.get_customer_by_id(db, current_user.customer_id)
    return schemas.CustomerResponse.model_validate(customer)


@router.get("", response_model=schemas.CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    customers, total = await service.list_customers(db, page, limit, sort_by, sort_order, search)
    return schemas.CustomerListResponse(
        items=[schemas.CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{customer_id}", response_model=schemas.CustomerResponse)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    customer = await service.get_customer_by_id(db, customer_id)
    return schemas.CustomerResponse.model_validate(customer)


@router.post("", response_model=schemas.CustomerResponse, status_code=201)
async def create_customer(
    data: schemas.CustomerCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    customer = await service.create_customer(db, **data.model_dump())
    return schemas.CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=schemas.CustomerResponse)
async def update_customer(
    customer_id: int,
    data: schemas.CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    customer = await service.update_customer(db, customer_id, **data.model_dump(exclude_unset=True))
    return schemas.CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_customer(db, customer_id)
