"""
Endpoints для аутентификации
Регистрация, логин, logout
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from collections import defaultdict

from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
)
from app.core.ratelimit import check_rate_limit
from app.core.config import settings
from app.db.session import get_db_connection
from app.core.otel_utils import db_span
from app.models.user import (
    GradeEnum,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserProfile,
    UserRoleEnum,
    UserStats,
    row_to_user_profile,
)

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate, conn: asyncpg.Connection = Depends(get_db_connection)
):
    # Проверяем существование пользователя
    with db_span("db.fetchrow", query="SELECT id FROM users WHERE username = $1 OR email = $2", params=[user_data.username, user_data.email]):
        existing_user = await conn.fetchrow(
            "SELECT id FROM users WHERE username = $1 OR email = $2",
            user_data.username,
            user_data.email,
        )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем или email уже существует",
        )

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = get_password_hash(user_data.password)
    now = datetime.now(timezone.utc)

    # Вставляем нового пользователя
    with db_span("db.execute", query="INSERT INTO users (...) VALUES (...)", params=[user_id, user_data.username, user_data.email]):
        await conn.execute(
        """
        INSERT INTO users (
            id, username, email, password_hash, role, level, grade, xp, xp_to_next,
            stats_int, stats_dex, stats_cha, badges, bio, skills, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        """,
        user_id,
        user_data.username,
        user_data.email,
        password_hash,
        user_data.role.value,
        1,
        GradeEnum.novice.value,
        0,
        100,
        10,
        10,
        10,
        "[]",
        None,
        "[]",
        now,
        now,
    )

    user_profile = UserProfile(
        id=user_id,
        username=user_data.username,
        email=user_data.email,
        role=user_data.role,
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(int=10, dex=10, cha=10),
        badges=[],
        created_at=now,
        updated_at=now,
    )

    access_token = create_access_token(data={"sub": user_id})

    # Create refresh token and set it as httpOnly cookie
    refresh_token, expires_seconds = create_refresh_token(user_id)

    resp = TokenResponse(
        access_token=access_token, token_type="bearer", user=user_profile
    )

    response = JSONResponse(
        content=json.loads(resp.model_dump_json(by_alias=True)),
        status_code=status.HTTP_201_CREATED,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=expires_seconds,
        path="/",
    )
    return response


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    # Enforce Redis-backed rate limit for login attempts
    check_rate_limit(request.client.host if request.client else "unknown", action="login", limit=10, window_seconds=300)

    with db_span("db.fetchrow", query="SELECT * FROM users WHERE username = $1", params=[credentials.username]):
        user_row = await conn.fetchrow(
            "SELECT * FROM users WHERE username = $1", credentials.username
        )

    if not user_row or not verify_password(
        credentials.password, user_row["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
        )

    user_profile = row_to_user_profile(user_row)

    access_token = create_access_token(data={"sub": user_row["id"]})

    # issue refresh token and set as httpOnly cookie
    refresh_token, expires_seconds = create_refresh_token(user_row["id"])

    resp = TokenResponse(
        access_token=access_token, token_type="bearer", user=user_profile
    )

    response = JSONResponse(
        content=json.loads(resp.model_dump_json(by_alias=True)),
        status_code=200,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=expires_seconds,
        path="/",
    )
    return response


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout: revoke refresh token (if present) and clear cookie."""
    refresh = request.cookies.get("refresh_token")
    if refresh:
        revoke_refresh_token(refresh)
    # clear cookie
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Успешный выход"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Rotate refresh token and return a new access token.

    Cookie `refresh_token` is required. The endpoint will rotate the refresh token
    (revoke the previous one and issue a new one) and set it as an httpOnly cookie.
    """
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    user_id = verify_refresh_token(refresh)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # rotate
    revoke_refresh_token(refresh)
    new_refresh, expires_seconds = create_refresh_token(user_id)

    # load user profile
    with db_span("db.fetchrow", query="SELECT * FROM users WHERE id = $1", params=[user_id]):
        user_row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not user_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_profile = row_to_user_profile(user_row)

    access_token = create_access_token(data={"sub": user_id})

    resp = TokenResponse(access_token=access_token, token_type="bearer", user=user_profile)

    response = JSONResponse(
        content=json.loads(resp.model_dump_json(by_alias=True)),
        status_code=200,
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=expires_seconds,
        path="/",
    )
    return response
