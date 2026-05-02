from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from app.users.models import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    # UserRole enum here gives Pydantic v2 a closed set: unknown role values
    # return 422 before the route handler runs (instead of the previous str
    # path that 500'd inside SQLAlchemy on unknown values).
    role: UserRole = UserRole.simple_user
    is_active: bool = True
    customer_id: Optional[int] = None
    discount_percent: Decimal = Field(default=0, ge=0, le=100)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    customer_id: Optional[int] = None
    discount_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)


class UserResponse(BaseModel):
    id: int
    email: str
    role: UserRole
    is_active: bool
    customer_id: Optional[int] = None
    discount_percent: Decimal = Decimal("0")
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    limit: int
