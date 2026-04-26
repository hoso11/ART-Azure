from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.dependencies import get_current_user
from app.users.models import User
from app.users.service import get_user_by_email, verify_password
from app.auth import service as auth_service
from app.auth.schemas import LoginRequest, AuthResponse
from app.exceptions import UnauthorizedException

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        logger.warning("auth.login_failed", email=data.email)
        raise UnauthorizedException(detail="Invalid email or password", code="invalid_credentials")

    if not user.is_active:
        logger.warning("auth.login_inactive", email=data.email)
        raise UnauthorizedException(detail="Account is deactivated", code="account_inactive")

    access_token = auth_service.create_access_token(user.id, user.role.value)
    refresh_token = auth_service.create_refresh_token(user.id, user.role.value)

    response_data = AuthResponse(
        message="Login successful",
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )

    response = JSONResponse(content=response_data.model_dump())
    auth_service.set_auth_cookies(response, access_token, refresh_token)

    logger.info("auth.login_success", user_id=user.id, role=user.role.value)
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse(content={"message": "Logged out"})
    auth_service.clear_auth_cookies(response)
    logger.info("auth.logout")
    return response


@router.post("/refresh")
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise UnauthorizedException(detail="No refresh token", code="no_refresh_token")

    payload = auth_service.decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedException(detail="Invalid refresh token", code="invalid_refresh_token")

    user_id = int(payload["sub"])
    role = payload["role"]

    from app.users.service import get_user_by_id
    user = await get_user_by_id(db, user_id)

    if not user.is_active:
        raise UnauthorizedException(detail="Account deactivated", code="account_inactive")

    new_access = auth_service.create_access_token(user.id, user.role.value)
    new_refresh = auth_service.create_refresh_token(user.id, user.role.value)

    response = JSONResponse(content={"message": "Token refreshed"})
    auth_service.set_auth_cookies(response, new_access, new_refresh)
    return response


@router.get("/me", response_model=AuthResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return AuthResponse(
        message="Authenticated",
        user_id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
    )
