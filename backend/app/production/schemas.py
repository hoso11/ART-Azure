from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.production.models import StageName, StageStatus


# ── Order-based ProductionStage ──────────────────────────

class ProductionStageCreate(BaseModel):
    """Used by POST /orders/{order_id}/stages to seed all five stages."""
    pass


class ProductionStageUpdate(BaseModel):
    """Move a stage forward — admin sets the next stage_name."""
    stage_name: StageName


class StageStatusUpdate(BaseModel):
    """Change just the status of a stage (pending → in_progress → completed)."""
    status: StageStatus
    note: Optional[str] = None


class OrderCurrentUpdate(BaseModel):
    """Set the displayed (current_stage, current_status) for an order. Plain
    str so the service layer can raise a typed ValidationException with a
    `code` field on bad values."""
    current_stage: str
    current_status: str
    note: Optional[str] = None


class ProductionLogResponse(BaseModel):
    id: int
    production_stage_id: int
    changed_by: int
    previous_status: StageStatus
    new_status: StageStatus
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductionStageResponse(BaseModel):
    id: int
    order_id: int
    stage_name: StageName
    status: StageStatus
    assigned_to: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    logs: list[ProductionLogResponse] = []

    model_config = {"from_attributes": True}


class ProductionStageListResponse(BaseModel):
    items: list[ProductionStageResponse]
    total: int
    page: int
    limit: int


# ── Stock-based production batch schemas ─────────────────

class ProductionBatchCreate(BaseModel):
    product_id: int
    variant_id: int
    quantity_to_produce: int


class ProductionBatchUpdate(BaseModel):
    current_stage: Optional[str] = None
    stage_status: Optional[str] = None


class BatchCompleteRequest(BaseModel):
    """Finalize a stock-based batch with a partial outcome.
    Service enforces:
      - good_quantity >= 0
      - damaged_quantity >= 0
      - good_quantity + damaged_quantity == quantity_to_produce
    """
    good_quantity: int
    damaged_quantity: int
    defect_reason: Optional[str] = None


class ProductionBatchProduct(BaseModel):
    id: int
    name: str
    sku: str

    model_config = {"from_attributes": True}


class ProductionBatchVariant(BaseModel):
    id: int
    size: str
    color: str

    model_config = {"from_attributes": True}


class ProductionBatchResponse(BaseModel):
    id: int
    product_id: int
    variant_id: int
    quantity_to_produce: int
    production_type: str
    current_stage: str
    stage_status: str
    materials_deducted: bool
    stock_added: bool
    good_quantity: int = 0
    damaged_quantity: int = 0
    defect_reason: Optional[str] = None
    created_by: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    product: Optional[ProductionBatchProduct] = None
    variant: Optional[ProductionBatchVariant] = None

    model_config = {"from_attributes": True}


class ProductionBatchListResponse(BaseModel):
    items: list[ProductionBatchResponse]
    total: int
    page: int
    limit: int
