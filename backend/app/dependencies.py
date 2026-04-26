from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth.service import decode_token
from app.users.models import User
from app.exceptions import UnauthorizedException, ForbiddenException


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise UnauthorizedException()

    payload = decode_token(token)
    if payload is None:
        raise UnauthorizedException(detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedException(detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise UnauthorizedException(detail="User not found or inactive")

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "admin":
        raise ForbiddenException(detail="Admin access required")
    return current_user


async def require_authenticated(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
