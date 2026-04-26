from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    product_variant_id: int
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0)
    notes: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_variant_id: int
    quantity: int
    unit_price: Decimal
    notes: Optional[str] = None

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
