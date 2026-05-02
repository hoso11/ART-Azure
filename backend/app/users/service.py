from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from passlib.context import CryptContext

from app.users.models import User, UserRole
from app.exceptions import NotFoundException, ConflictException, ForbiddenException, ValidationException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Authorization helpers (load-bearing — see CLAUDE.md RBAC section) ──────

def can_assign_role(actor: User, target_role: UserRole) -> bool:
    """Whether `actor` is permitted to set/leave a user's role to `target_role`.

    - admin    → may assign any role
    - director → may assign only `simple_user`
    - others   → never (their routes are denied at the dependency layer
      anyway, but this is the second wall in defense-in-depth)
    """
    if actor.role == UserRole.admin:
        return True
    if actor.role == UserRole.director:
        return target_role == UserRole.simple_user
    return False


def can_manage_user(actor: User, target: User) -> bool:
    """Whether `actor` may view / mutate the `target` user.

    - admin    → any user
    - director → only users whose current role is simple_user
    - others   → never
    """
    if actor.role == UserRole.admin:
        return True
    if actor.role == UserRole.director:
        return target.role == UserRole.simple_user
    return False


async def count_active_admins(db: AsyncSession) -> int:
    """Count of active admin users. Used by the last-admin guard."""
    result = await db.execute(
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.admin, User.is_active == True)  # noqa: E712
    )
    return int(result.scalar() or 0)


async def is_last_active_admin(db: AsyncSession, user: User) -> bool:
    """True iff `user` is the only currently-active admin."""
    if user.role != UserRole.admin or not user.is_active:
        return False
    return (await count_active_admins(db)) <= 1


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException(detail=f"User with id {user_id} not found")
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def list_users(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    search: str | None = None,
    restrict_to_role: UserRole | None = None,
) -> tuple[list[User], int]:
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if restrict_to_role is not None:
        query = query.where(User.role == restrict_to_role)
        count_query = count_query.where(User.role == restrict_to_role)

    if search:
        query = query.where(User.email.ilike(f"%{search}%"))
        count_query = count_query.where(User.email.ilike(f"%{search}%"))

    sort_col = getattr(User, sort_by, User.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    users = list(result.scalars().all())

    return users, total


async def create_user(db: AsyncSession, email: str, password: str, role: str = "simple_user", customer_id: int | None = None, discount_percent=0) -> User:
    existing = await get_user_by_email(db, email)
    if existing:
        raise ConflictException(detail=f"User with email {email} already exists")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=role,
        customer_id=customer_id,
        discount_percent=discount_percent,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: int, **kwargs) -> User:
    user = await get_user_by_id(db, user_id)

    if "password" in kwargs and kwargs["password"]:
        kwargs["hashed_password"] = hash_password(kwargs.pop("password"))
    else:
        kwargs.pop("password", None)

    for key, value in kwargs.items():
        if value is not None:
            setattr(user, key, value)

    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> None:
    user = await get_user_by_id(db, user_id)
    user.is_active = False
    await db.flush()
