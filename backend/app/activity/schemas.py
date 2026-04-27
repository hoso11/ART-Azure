from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ActivityLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    user_email: str | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    old_values: dict | None = None
    new_values: dict | None = None
    details: str | None = None
    ip_address: str | None = None
    created_at: datetime


class ActivityLogListResponse(BaseModel):
    items: list[ActivityLogResponse]
    total: int
    page: int
    limit: int
