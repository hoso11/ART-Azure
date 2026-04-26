from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.activity.models import ActivityLog


async def log_activity(
    db: AsyncSession,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    metadata: dict | None = None,
) -> ActivityLog:
    log = ActivityLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_=metadata,
    )
    db.add(log)
    await db.flush()
    return log


async def list_activities(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    user_id: int | None = None,
    entity_type: str | None = None,
) -> tuple[list[ActivityLog], int]:
    query = select(ActivityLog).order_by(ActivityLog.created_at.desc())
    count_query = select(func.count()).select_from(ActivityLog)

    if user_id:
        query = query.where(ActivityLog.user_id == user_id)
        count_query = count_query.where(ActivityLog.user_id == user_id)

    if entity_type:
        query = query.where(ActivityLog.entity_type == entity_type)
        count_query = count_query.where(ActivityLog.entity_type == entity_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all()), total
