from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class MaterialCreate(BaseModel):
    name: str
    sku: str
    unit: str
    quantity_on_hand: Decimal = Field(default=0, ge=0)
    low_stock_threshold: Decimal = Field(default=0, ge=0)
    description: Optional[str] = None


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    unit: Optional[str] = None
    quantity_on_hand: Optional[Decimal] = Field(default=None, ge=0)
    low_stock_threshold: Optional[Decimal] = Field(default=None, ge=0)
    description: Optional[str] = None


class InventoryResponse(BaseModel):
    id: int
    material_id: int
    quantity_on_hand: Decimal
    last_updated: datetime

    model_config = {"from_attributes": True}


class MaterialResponse(BaseModel):
    id: int
    name: str
    sku: str
    unit: str
    low_stock_threshold: Decimal
    description: Optional[str] = None
    inventory: Optional[InventoryResponse] = None

    model_config = {"from_attributes": True}


class MaterialListResponse(BaseModel):
    items: list[MaterialResponse]
    total: int
    page: int
    limit: int


class StockMovementCreate(BaseModel):
    material_id: int
    quantity_change: Decimal
    reason: str
    order_id: Optional[int] = None


class StockMovementResponse(BaseModel):
    id: int
    material_id: int
    order_id: Optional[int] = None
    quantity_change: Decimal
    reason: str
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class StockMovementListResponse(BaseModel):
    items: list[StockMovementResponse]
    total: int
    page: int
    limit: int
