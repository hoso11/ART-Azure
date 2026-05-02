from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin, require_authenticated, require_roles, CUSTOMER_MANAGEMENT
from app.customers import service, schemas
from app.customers.models import Customer
from app.users.models import User
from app.activity import service as activity_service

router = APIRouter(prefix="/customers", tags=["Customers"])


def _customer_snapshot(c: Customer) -> dict:
    return {
        "name": c.name,
        "company_name": c.company_name,
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "is_active": c.is_active,
    }


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
    _admin: User = Depends(require_roles(*CUSTOMER_MANAGEMENT)),
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
    _admin: User = Depends(require_roles(*CUSTOMER_MANAGEMENT)),
):
    customer = await service.get_customer_by_id(db, customer_id)
    return schemas.CustomerResponse.model_validate(customer)


@router.post("", response_model=schemas.CustomerResponse, status_code=201)
async def create_customer(
    data: schemas.CustomerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*CUSTOMER_MANAGEMENT)),
):
    customer = await service.create_customer(db, **data.model_dump())
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="customer.created", entity_type="customer", entity_id=customer.id,
        new_values=_customer_snapshot(customer),
    )
    return schemas.CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=schemas.CustomerResponse)
async def update_customer(
    customer_id: int,
    data: schemas.CustomerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*CUSTOMER_MANAGEMENT)),
):
    existing = await service.get_customer_by_id(db, customer_id)
    old_snapshot = _customer_snapshot(existing)

    customer = await service.update_customer(db, customer_id, **data.model_dump(exclude_unset=True))
    new_snapshot = _customer_snapshot(customer)

    if old_snapshot != new_snapshot:
        await activity_service.log_activity(
            db, user=admin, request=request,
            action="customer.updated", entity_type="customer", entity_id=customer.id,
            old_values=old_snapshot, new_values=new_snapshot,
        )
    return schemas.CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*CUSTOMER_MANAGEMENT)),
):
    existing = await service.get_customer_by_id(db, customer_id)
    snapshot = _customer_snapshot(existing)
    await service.delete_customer(db, customer_id)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="customer.deleted", entity_type="customer", entity_id=customer_id,
        old_values=snapshot,
        details=f"Deleted {existing.name}",
    )
