from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    product_variant_id: int
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0)
    notes: Optional[str] = None


class OrderItemProductBrief(BaseModel):
    id: int
    name: str
    sku: str

    model_config = {"from_attributes": True}


class OrderItemVariantBrief(BaseModel):
    id: int
    size: str
    color: str
    stock_quantity: int = 0
    product: Optional[OrderItemProductBrief] = None

    model_config = {"from_attributes": True}


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    # Nullable since migration 015_variant_force_delete — admin force-delete
    # of a ProductVariant snapshots the variant + product name onto the row
    # and NULLs this FK. UI falls back to variant_name_snapshot +
    # product_name_snapshot with the "(ջնջված)" marker.
    product_variant_id: Optional[int] = None
    variant_name_snapshot: Optional[str] = None
    product_name_snapshot: Optional[str] = None
    quantity: int
    unit_price: Decimal
    notes: Optional[str] = None
    fulfilled_from_stock: int = 0
    production_quantity: int = 0
    product_variant: Optional[OrderItemVariantBrief] = None

    model_config = {"from_attributes": True}


class CustomerBrief(BaseModel):
    id: int
    name: str
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    customer_id: int
    priority: str = "normal"
    deadline: Optional[datetime] = None
    notes: Optional[str] = None
    items: list[OrderItemCreate] = []


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    deadline: Optional[datetime] = None
    notes: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    status: str


class OrderResponse(BaseModel):
    id: int
    customer_id: int
    created_by: int
    status: str
    priority: str
    deadline: Optional[datetime] = None
    notes: Optional[str] = None
    stock_deducted: bool = False
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse] = []
    customer: Optional[CustomerBrief] = None

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    limit: int
