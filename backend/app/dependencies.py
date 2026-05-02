from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth.service import decode_token
from app.users.models import User, UserRole
from app.exceptions import UnauthorizedException, ForbiddenException


# ── Role groups (load-bearing — used by every router) ──────────────────────
# Centralized so the matrix is grep-able from one place. Routers should
# prefer these constants over inline tuples.

ADMIN_ONLY: tuple[UserRole, ...] = (UserRole.admin,)

# Anyone allowed to use the /users page. Director sees only simple_user
# accounts (filtered server-side in users.service.list_users).
USER_MANAGEMENT: tuple[UserRole, ...] = (UserRole.admin, UserRole.director)

# Business management view: orders / production / products. Used by admin,
# director, and production_manager.
BUSINESS_MANAGER: tuple[UserRole, ...] = (
    UserRole.admin,
    UserRole.director,
    UserRole.production_manager,
)

# Order viewers: same as BUSINESS_MANAGER plus simple_user (who is scoped
# to their own customer in the handler). Excludes warehouse_manager.
ORDERS_VIEW: tuple[UserRole, ...] = (
    UserRole.admin,
    UserRole.director,
    UserRole.production_manager,
    UserRole.simple_user,
)

# Product viewers: same shape as ORDERS_VIEW. simple_user gets discount
# applied in the handler. Warehouse_manager has no product visibility.
PRODUCTS_VIEW: tuple[UserRole, ...] = (
    UserRole.admin,
    UserRole.director,
    UserRole.production_manager,
    UserRole.simple_user,
)

# Inventory write — admin, director, warehouse_manager. Production_manager
# gets read-only on /inventory/materials* via PRODUCTION_INVENTORY_READ below.
INVENTORY_MANAGER: tuple[UserRole, ...] = (
    UserRole.admin,
    UserRole.director,
    UserRole.warehouse_manager,
)

# Read-only material access for the production planning flow.
PRODUCTION_INVENTORY_READ: tuple[UserRole, ...] = (
    UserRole.admin,
    UserRole.director,
    UserRole.warehouse_manager,
    UserRole.production_manager,
)

# Customers: admin + director only. Production / warehouse managers do not
# need customer access.
CUSTOMER_MANAGEMENT: tuple[UserRole, ...] = (UserRole.admin, UserRole.director)

# Reports — admin + director see everything. PM gets the three production
# reports (handled via PRODUCTION_REPORTS below).
REPORT_MANAGEMENT: tuple[UserRole, ...] = (UserRole.admin, UserRole.director)

PRODUCTION_REPORTS: tuple[UserRole, ...] = (
    UserRole.admin,
    UserRole.director,
    UserRole.production_manager,
)

# Activity log: admin + director.
ACTIVITY_VIEW: tuple[UserRole, ...] = (UserRole.admin, UserRole.director)


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


def require_roles(*allowed: UserRole):
    """Dependency factory: 403 unless current_user.role is in `allowed`.

    Usage:
        @router.get("/foo")
        async def foo(
            _user: User = Depends(require_roles(UserRole.admin, UserRole.director)),
        ): ...

    Or with a pre-defined group constant:
        admin: User = Depends(require_roles(*USER_MANAGEMENT))
    """
    if not allowed:
        raise RuntimeError("require_roles called with no roles — would deny everything")
    allowed_set = frozenset(allowed)

    async def _dep(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_set:
            raise ForbiddenException(
                detail="Insufficient permissions",
                code="insufficient_permissions",
            )
        return current_user

    return _dep


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.admin:
        raise ForbiddenException(detail="Admin access required")
    return current_user


async def require_authenticated(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
