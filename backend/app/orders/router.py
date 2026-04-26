from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin, require_authenticated
from app.orders import service, schemas
from app.users.models import User

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("", response_model=schemas.OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = Query(None),
    status: str | None = Query(None),
    customer_id: int | None = Query(None),
    filter: str | None = Query(None, pattern="^(active|delayed)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_authenticated),
):
    # Simple users can only see their own orders
    if current_user.role.value == "simple_user":
        if current_user.customer_id is None:
            return schemas.OrderListResponse(items=[], total=0, page=page, limit=limit)
        customer_id = current_user.customer_id

    orders, total = await service.list_orders(db, page, limit, sort_by, sort_order, search, status, customer_id, filter)
    return schemas.OrderListResponse(
        items=[schemas.OrderResponse.model_validate(o) for o in orders],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/stats")
async def get_order_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return await service.get_order_stats(db)


@router.get("/{order_id}", response_model=schemas.OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_authenticated),
):
    order = await service.get_order_by_id(db, order_id)

    # Simple users can only see their own orders
    if current_user.role.value == "simple_user" and order.customer_id != current_user.customer_id:
        from app.exceptions import ForbiddenException
        raise ForbiddenException(detail="Access denied to this order")

    return schemas.OrderResponse.model_validate(order)


@router.post("", response_model=schemas.OrderResponse, status_code=201)
async def create_order(
    data: schemas.OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_authenticated),
):
    # Simple users can only create orders for their own customer
    if current_user.role.value == "simple_user":
        if current_user.customer_id is None:
            from app.exceptions import ForbiddenException
            raise ForbiddenException(detail="No customer account linked")
        data.customer_id = current_user.customer_id

    items = [item.model_dump() for item in data.items]
    dump = data.model_dump()
    dump.pop("items")
    order = await service.create_order(db, created_by=current_user.id, items=items, **dump)
    return schemas.OrderResponse.model_validate(order)


@router.patch("/{order_id}", response_model=schemas.OrderResponse)
async def update_order(
    order_id: int,
    data: schemas.OrderUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    order = await service.update_order(db, order_id, **data.model_dump(exclude_unset=True))
    return schemas.OrderResponse.model_validate(order)


@router.patch("/{order_id}/status", response_model=schemas.OrderResponse)
async def update_order_status(
    order_id: int,
    data: schemas.OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    order = await service.update_order(db, order_id, status=data.status)
    return schemas.OrderResponse.model_validate(order)


@router.delete("/{order_id}", status_code=204)
async def delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_order(db, order_id)


@router.post("/{order_id}/items", response_model=schemas.OrderItemResponse, status_code=201)
async def add_order_item(
    order_id: int,
    data: schemas.OrderItemCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    item = await service.add_order_item(db, order_id, **data.model_dump())
    return schemas.OrderItemResponse.model_validate(item)


@router.delete("/items/{item_id}", status_code=204)
async def delete_order_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await service.delete_order_item(db, item_id)
