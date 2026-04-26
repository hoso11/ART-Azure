from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProductionStageCreate(BaseModel):
    order_id: int
    stage_name: str
    assigned_to: Optional[int] = None
    notes: Optional[str] = None


class ProductionStageUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[int] = None
    notes: Optional[str] = None


class StageStatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None


class ProductionLogResponse(BaseModel):
    id: int
    production_stage_id: int
    changed_by: int
    previous_status: str
    new_status: str
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductionStageResponse(BaseModel):
    id: int
    order_id: int
    stage_name: str
    status: str
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
