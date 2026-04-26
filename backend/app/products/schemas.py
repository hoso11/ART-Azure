from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


# ── Shared nested types ──────────────────────────────────

class MaterialInfo(BaseModel):
    id: int
    name: str
    unit: str
    model_config = {"from_attributes": True}


# ── Categories ──────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Variants ────────────────────────────────────────────

class VariantCreate(BaseModel):
    size: str
    color: str
    price: Decimal = Field(ge=0)
    stock_quantity: int = Field(ge=0, default=0)


class VariantUpdate(BaseModel):
    size: Optional[str] = None
    color: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    stock_quantity: Optional[int] = Field(default=None, ge=0)


class VariantResponse(BaseModel):
    id: int
    product_id: int
    size: str
    color: str
    price: Decimal
    stock_quantity: int

    model_config = {"from_attributes": True}


# ── Images ──────────────────────────────────────────────

class ImageResponse(BaseModel):
    id: int
    product_id: int
    storage_key: str
    is_primary: bool
    created_at: datetime
    url: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Product Materials ───────────────────────────────────

class ProductMaterialCreate(BaseModel):
    material_id: int
    quantity_required: Decimal = Field(ge=0)
    unit: str


class ProductMaterialResponse(BaseModel):
    id: int
    product_id: int
    material_id: int
    quantity_required: Decimal
    unit: str

    model_config = {"from_attributes": True}


# ── Product Size Material Requirements ──────────────────
# Per-product, per-size material consumption table.
# Columns: Material | Size | Quantity per item | (Unit from material)

class ProductSizeMaterialRequirementCreate(BaseModel):
    material_id: int
    size: str = Field(min_length=1)
    quantity_per_item: Decimal = Field(gt=0)


class ProductSizeMaterialRequirementUpdate(BaseModel):
    quantity_per_item: Decimal = Field(gt=0)


class ProductSizeMaterialRequirementResponse(BaseModel):
    id: int
    product_id: int
    material_id: int
    size: str
    quantity_per_item: Decimal
    material: Optional[MaterialInfo] = None

    model_config = {"from_attributes": True}


# ── Products ────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str
    sku: str
    category_id: Optional[int] = None
    description: Optional[str] = None
    technical_notes: Optional[str] = None
    variants: list[VariantCreate] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category_id: Optional[int] = None
    description: Optional[str] = None
    technical_notes: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    sku: str
    category_id: Optional[int] = None
    category: Optional[CategoryResponse] = None
    description: Optional[str] = None
    technical_notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    variants: list[VariantResponse] = []
    images: list[ImageResponse] = []

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    limit: int
