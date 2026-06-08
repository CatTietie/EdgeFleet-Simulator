"""Authentication endpoints."""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Depends
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User
from app.schemas import LoginRequest, TokenResponse, RefreshRequest
from app.dependencies import get_db

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory refresh token store (in production, use Redis)
_refresh_tokens: dict[str, dict] = {}


def _create_access_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "org_id": user.org_id,
        "group_ids": user.group_ids or [],
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _create_refresh_token(user_id: str) -> str:
    token = str(uuid.uuid4())
    _refresh_tokens[token] = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    }
    return token


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return TokenResponse(
        access_token=_create_access_token(user),
        refresh_token=_create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_data = _refresh_tokens.pop(body.refresh_token, None)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if datetime.now(timezone.utc) > token_data["exp"]:
        raise HTTPException(status_code=401, detail="Refresh token expired")

    result = await db.execute(select(User).where(User.id == token_data["user_id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=_create_access_token(user),
        refresh_token=_create_refresh_token(user.id),
    )
