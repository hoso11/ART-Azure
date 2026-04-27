from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = "simple_user"
    is_active: bool = True
    customer_id: Optional[int] = None
    discount_percent: Decimal = Field(default=0, ge=0, le=100)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    customer_id: Optional[int] = None
    discount_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
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
