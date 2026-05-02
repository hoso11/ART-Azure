from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    require_admin,
    require_authenticated,
    require_roles,
    BUSINESS_MANAGER,
    ORDERS_VIEW,
)
from app.orders import service, schemas
from app.orders.models import Order
from app.users.models import User, UserRole
from app.activity import service as activity_service

router = APIRouter(prefix="/orders", tags=["Orders"])


def _order_snapshot(o: Order) -> dict:
    return {
        "customer_id": o.customer_id,
        "status": o.status.value if hasattr(o.status, "value") else o.status,
        "priority": o.priority.value if hasattr(o.priority, "value") else o.priority,
        "deadline": o.deadline.isoformat() if o.deadline else None,
        "stock_deducted": o.stock_deducted,
    }


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
    current_user: User = Depends(require_roles(*ORDERS_VIEW)),
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
    _admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    return await service.get_order_stats(db)


@router.get("/{order_id}", response_model=schemas.OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*ORDERS_VIEW)),
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*ORDERS_VIEW)),
):
    # Simple users can only create orders for their own customer
    if current_user.role == UserRole.simple_user:
        if current_user.customer_id is None:
            from app.exceptions import ForbiddenException
            raise ForbiddenException(detail="No customer account linked")
        data.customer_id = current_user.customer_id

        # Server-side discount enforcement: override unit_price from DB
        from app.products.models import ProductVariant
        discount_factor = (Decimal("100") - Decimal(str(current_user.discount_percent or 0))) / Decimal("100")
        for item in data.items:
            result = await db.execute(
                sa_select(ProductVariant).where(ProductVariant.id == item.product_variant_id)
            )
            variant = result.scalar_one_or_none()
            if variant:
                item.unit_price = (variant.price * discount_factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    items = [item.model_dump() for item in data.items]
    dump = data.model_dump()
    dump.pop("items")
    order = await service.create_order(db, created_by=current_user.id, items=items, **dump)
    await activity_service.log_activity(
        db, user=current_user, request=request,
        action="order.created", entity_type="order", entity_id=order.id,
        new_values={
            **_order_snapshot(order),
            "item_count": len(order.items or []),
        },
    )
    return schemas.OrderResponse.model_validate(order)


@router.patch("/{order_id}", response_model=schemas.OrderResponse)
async def update_order(
    order_id: int,
    data: schemas.OrderUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    existing = await service.get_order_by_id(db, order_id)
    old_snapshot = _order_snapshot(existing)
    old_stock_deducted = existing.stock_deducted

    order = await service.update_order(db, order_id, admin_user_id=current_admin.id, **data.model_dump(exclude_unset=True))
    new_snapshot = _order_snapshot(order)

    if old_snapshot["status"] != new_snapshot["status"]:
        # Status change → one summary audit row that also captures whether
        # the stock-deduction side effect ran on this transition.
        details = None
        if not old_stock_deducted and order.stock_deducted:
            details = "Stock deducted on completion"
        await activity_service.log_activity(
            db, user=current_admin, request=request,
            action="order.status_changed", entity_type="order", entity_id=order.id,
            old_values={"status": old_snapshot["status"]},
            new_values={
                "status": new_snapshot["status"],
                "stock_deducted": order.stock_deducted,
            },
            details=details,
        )
    elif old_snapshot != new_snapshot:
        await activity_service.log_activity(
            db, user=current_admin, request=request,
            action="order.updated", entity_type="order", entity_id=order.id,
            old_values=old_snapshot, new_values=new_snapshot,
        )
    return schemas.OrderResponse.model_validate(order)


@router.patch("/{order_id}/status", response_model=schemas.OrderResponse)
async def update_order_status(
    order_id: int,
    data: schemas.OrderStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    existing = await service.get_order_by_id(db, order_id)
    old_status = existing.status.value if hasattr(existing.status, "value") else existing.status
    old_stock_deducted = existing.stock_deducted

    order = await service.update_order(db, order_id, admin_user_id=current_admin.id, status=data.status)
    new_status = order.status.value if hasattr(order.status, "value") else order.status

    if old_status != new_status:
        details = None
        if not old_stock_deducted and order.stock_deducted:
            details = "Stock deducted on completion"
        await activity_service.log_activity(
            db, user=current_admin, request=request,
            action="order.status_changed", entity_type="order", entity_id=order.id,
            old_values={"status": old_status},
            new_values={"status": new_status, "stock_deducted": order.stock_deducted},
            details=details,
        )
    return schemas.OrderResponse.model_validate(order)


@router.delete("/{order_id}", status_code=204)
async def delete_order(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    existing = await service.get_order_by_id(db, order_id)
    snapshot = _order_snapshot(existing)
    await service.delete_order(db, order_id)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="order.deleted", entity_type="order", entity_id=order_id,
        old_values=snapshot,
    )


@router.post("/{order_id}/items", response_model=schemas.OrderItemResponse, status_code=201)
async def add_order_item(
    order_id: int,
    data: schemas.OrderItemCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    item = await service.add_order_item(db, order_id, **data.model_dump())
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="order.item_added", entity_type="order", entity_id=order_id,
        new_values={
            "item_id": item.id,
            "product_variant_id": item.product_variant_id,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
        },
    )
    return schemas.OrderItemResponse.model_validate(item)


@router.delete("/items/{item_id}", status_code=204)
async def delete_order_item(
    item_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(*BUSINESS_MANAGER)),
):
    await service.delete_order_item(db, item_id)
    await activity_service.log_activity(
        db, user=admin, request=request,
        action="order.item_removed", entity_type="order_item", entity_id=item_id,
    )
