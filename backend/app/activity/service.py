from datetime import datetime
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.activity.models import ActivityLog
from app.users.models import User


def extract_ip(request: Request | None) -> str | None:
    """Honor X-Forwarded-For (set by nginx) so we record the real client IP
    rather than the proxy. Falls back to the direct peer address."""
    if request is None:
        return None
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # XFF is a comma-separated chain; the leftmost entry is the original client.
        return xff.split(",")[0].strip() or None
    return request.client.host if request.client else None


async def log_activity(
    db: AsyncSession,
    *,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    details: str | None = None,
    request: Request | None = None,
) -> ActivityLog | None:
    """Write an audit row. Never raises — a failure here must not break the
    user's mutation. user=None is allowed (failed logins, system actions)."""
    try:
        log = ActivityLog(
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            details=details,
            ip_address=extract_ip(request),
        )
        db.add(log)
        await db.flush()
        return log
    except Exception as e:
        logger.error("activity.log_failed", action=action, error=str(e))
        return None


async def list_activities(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    user_id: int | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> tuple[list[ActivityLog], int]:
    query = select(ActivityLog).order_by(ActivityLog.created_at.desc())
    count_query = select(func.count()).select_from(ActivityLog)

    if user_id is not None:
        query = query.where(ActivityLog.user_id == user_id)
        count_query = count_query.where(ActivityLog.user_id == user_id)

    if entity_type:
        query = query.where(ActivityLog.entity_type == entity_type)
        count_query = count_query.where(ActivityLog.entity_type == entity_type)

    if action:
        query = query.where(ActivityLog.action == action)
        count_query = count_query.where(ActivityLog.action == action)

    if from_date is not None:
        query = query.where(ActivityLog.created_at >= from_date)
        count_query = count_query.where(ActivityLog.created_at >= from_date)

    if to_date is not None:
        query = query.where(ActivityLog.created_at <= to_date)
        count_query = count_query.where(ActivityLog.created_at <= to_date)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all()), total
