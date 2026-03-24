from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db_session
from src.core.deps import get_current_user
from src.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    decode_token,
)
from src.models.models import AppUser
from src.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserPublic

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserPublic,
    summary="Register a new user",
    description="Creates a new user account with email/password.",
)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_db_session)) -> UserPublic:
    existing = (await session.execute(select(AppUser).where(AppUser.email == str(req.email)))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = AppUser(
        email=str(req.email),
        display_name=req.display_name,
        password_hash=hash_password(req.password),
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserPublic.model_validate(user, from_attributes=True)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Login",
    description="Authenticate with email/password and receive access/refresh tokens.",
)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_db_session)) -> TokenPair:
    user = (await session.execute(select(AppUser).where(AppUser.email == str(req.email)))).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")

    return TokenPair(
        access_token=create_access_token(user_id=user.id),
        refresh_token=create_refresh_token(user_id=user.id),
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Refresh tokens",
    description="Exchange a refresh token for a new access token (and refresh token).",
)
async def refresh(req: RefreshRequest) -> TokenPair:
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Note: for simplicity we are not storing refresh tokens server-side.
    return TokenPair(
        access_token=create_access_token(user_id=user_id),
        refresh_token=create_refresh_token(user_id=user_id),
    )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current user",
    description="Returns the authenticated user's profile.",
)
async def me(current_user: AppUser = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(current_user, from_attributes=True)
