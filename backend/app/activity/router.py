from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_roles, ACTIVITY_VIEW
from app.activity import service, schemas
from app.users.models import User

router = APIRouter(prefix="/activity-logs", tags=["Activity"])


@router.get("", response_model=schemas.ActivityLogListResponse)
async def list_activity_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(None),
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles(*ACTIVITY_VIEW)),
):
    items, total = await service.list_activities(
        db,
        page=page,
        limit=limit,
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        from_date=from_date,
        to_date=to_date,
    )
    return schemas.ActivityLogListResponse(
        items=[schemas.ActivityLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        limit=limit,
    )
