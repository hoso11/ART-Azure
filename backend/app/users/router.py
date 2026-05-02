from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_roles, USER_MANAGEMENT
from app.exceptions import ForbiddenException, ValidationException
from app.users import service, schemas
from app.users.models import User, UserRole
from app.activity import service as activity_service

router = APIRouter(prefix="/users", tags=["Users"])


def _user_snapshot(u: User) -> dict:
    """Audit-safe snapshot. Never includes the password hash."""
    return {
        "email": u.email,
        "role": u.role.value if hasattr(u.role, "value") else u.role,
        "customer_id": u.customer_id,
        "discount_percent": float(u.discount_percent) if u.discount_percent is not None else 0,
        "is_active": u.is_active,
    }


def _restrict_for(actor: User) -> UserRole | None:
    """Director sees only simple_user accounts. Admin sees everything.

    Returning a UserRole means "filter to this role only" in
    service.list_users; None means "no filter".
    """
    if actor.role == UserRole.director:
        return UserRole.simple_user
    return None


def _ensure_can_manage(actor: User, target: User) -> None:
    """Raise 403 if actor cannot manage target (director probing higher roles)."""
    if not service.can_manage_user(actor, target):
        raise ForbiddenException(
            detail="You cannot manage this user",
            code="user_management_denied",
        )


def _ensure_can_assign_role(actor: User, target_role: UserRole) -> None:
    if not service.can_assign_role(actor, target_role):
        raise ForbiddenException(
            detail=f"You cannot assign role '{target_role.value}'",
            code="role_assignment_denied",
        )


@router.get("", response_model=schemas.UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(*USER_MANAGEMENT)),
):
    users, total = await service.list_users(
        db, page, limit, sort_by, sort_order, search,
        restrict_to_role=_restrict_for(actor),
    )
    return schemas.UserListResponse(
        items=[schemas.UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{user_id}", response_model=schemas.UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(*USER_MANAGEMENT)),
):
    user = await service.get_user_by_id(db, user_id)
    _ensure_can_manage(actor, user)
    return schemas.UserResponse.model_validate(user)


@router.post("", response_model=schemas.UserResponse, status_code=201)
async def create_user(
    data: schemas.UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(*USER_MANAGEMENT)),
):
    # Guard 1: actor must be allowed to assign the requested role.
    _ensure_can_assign_role(actor, data.role)

    user = await service.create_user(
        db, data.email, data.password, data.role, data.customer_id, data.discount_percent
    )
    await activity_service.log_activity(
        db, user=actor, request=request,
        action="user.created", entity_type="user", entity_id=user.id,
        new_values=_user_snapshot(user),
    )
    return schemas.UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=schemas.UserResponse)
async def update_user(
    user_id: int,
    data: schemas.UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(*USER_MANAGEMENT)),
):
    payload = data.model_dump(exclude_unset=True)
    password_changed = bool(payload.get("password"))

    existing = await service.get_user_by_id(db, user_id)

    # Guard 1: actor must be able to manage this target user.
    _ensure_can_manage(actor, existing)

    is_self = (existing.id == actor.id)

    # Guard 2: nobody changes their own role (admin → admin no-op is fine,
    # but any actual role transition on self is denied).
    if is_self and "role" in payload and payload["role"] != existing.role:
        raise ForbiddenException(
            detail="You cannot change your own role",
            code="self_role_change_denied",
        )

    # Guard 3: nobody deactivates themselves.
    if is_self and "is_active" in payload and payload["is_active"] is False:
        raise ForbiddenException(
            detail="You cannot deactivate your own account",
            code="self_deactivation_denied",
        )

    # Guard 4: if a role change is requested, actor must be allowed to
    # assign the new role.
    if "role" in payload and payload["role"] is not None:
        new_role = payload["role"]
        if not isinstance(new_role, UserRole):
            new_role = UserRole(new_role)
        _ensure_can_assign_role(actor, new_role)

    # Guard 5: last-active-admin protection. Refuse if this update would
    # demote the only active admin or deactivate them.
    if await service.is_last_active_admin(db, existing):
        will_demote = (
            "role" in payload
            and payload["role"] is not None
            and payload["role"] != UserRole.admin
        )
        will_deactivate = "is_active" in payload and payload["is_active"] is False
        if will_demote or will_deactivate:
            raise ValidationException(
                detail="Cannot demote or deactivate the last active admin",
                code="last_admin_required",
            )

    old_snapshot = _user_snapshot(existing)
    old_discount = float(existing.discount_percent) if existing.discount_percent is not None else 0

    user = await service.update_user(db, user_id, **payload)
    new_snapshot = _user_snapshot(user)
    new_discount = float(user.discount_percent) if user.discount_percent is not None else 0

    # Diff non-sensitive fields. Skip if nothing actually changed.
    if old_snapshot != new_snapshot:
        await activity_service.log_activity(
            db, user=actor, request=request,
            action="user.updated", entity_type="user", entity_id=user.id,
            old_values=old_snapshot, new_values=new_snapshot,
        )

    if old_discount != new_discount:
        await activity_service.log_activity(
            db, user=actor, request=request,
            action="user.discount_changed", entity_type="user", entity_id=user.id,
            old_values={"discount_percent": old_discount},
            new_values={"discount_percent": new_discount},
        )

    if password_changed:
        # Sensitive — never include any value.
        await activity_service.log_activity(
            db, user=actor, request=request,
            action="user.password_changed", entity_type="user", entity_id=user.id,
            details="Password changed",
        )

    return schemas.UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(*USER_MANAGEMENT)),
):
    existing = await service.get_user_by_id(db, user_id)

    _ensure_can_manage(actor, existing)

    if existing.id == actor.id:
        raise ForbiddenException(
            detail="You cannot deactivate your own account",
            code="self_deactivation_denied",
        )

    if await service.is_last_active_admin(db, existing):
        raise ValidationException(
            detail="Cannot deactivate the last active admin",
            code="last_admin_required",
        )

    snapshot = _user_snapshot(existing)
    await service.delete_user(db, user_id)
    await activity_service.log_activity(
        db, user=actor, request=request,
        action="user.deleted", entity_type="user", entity_id=user_id,
        old_values=snapshot,
        details=f"Soft-deleted {existing.email}",
    )
