"""
Endpoints для аутентификации
Регистрация, логин, logout
"""

import json
import uuid
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    RefreshTokenStoreUnavailableError,
)
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.core.config import settings
from app.db.session import get_db_connection
from app.core.otel_utils import db_span
from app.api.deps import _USER_SAFE_COLUMNS
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

# Login needs password_hash in addition to safe columns
_USER_AUTH_COLUMNS = f"{_USER_SAFE_COLUMNS}, password_hash"

AUTH_SERVICE_UNAVAILABLE_DETAIL = "Authentication service temporarily unavailable"


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: Request,
    user_data: UserCreate, conn: asyncpg.Connection = Depends(get_db_connection)
):
    await check_rate_limit(get_client_ip(request), action="register", limit=5, window_seconds=60, request=request)
    # Проверяем существование пользователя
    with db_span("db.fetchrow", query="SELECT id FROM users WHERE username = $1 OR email = $2", params=[user_data.username, user_data.email]):
        existing_user = await conn.fetchrow(
            "SELECT id FROM users WHERE username = $1 OR email = $2",
            user_data.username,
            user_data.email,
        )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось создать аккаунт. Попробуйте другие данные.",
        )

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = get_password_hash(user_data.password)
    now = datetime.now(timezone.utc)

    # Role safety is enforced by UserCreate.prevent_admin_registration validator
    safe_role = user_data.role

    # Вставляем нового пользователя (wrapped in transaction for atomicity)
    async with conn.transaction():
        with db_span("db.execute", query="INSERT INTO users (...) VALUES (...)", params=[user_id, user_data.username, user_data.email]):
            await conn.execute(
            """
            INSERT INTO users (
                id, username, email, password_hash, role, level, grade, xp, xp_to_next,
                stats_int, stats_dex, stats_cha, stat_points, badges, bio, skills, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            """,
            user_id,
            user_data.username,
            user_data.email,
            password_hash,
            safe_role.value,
            1,
            GradeEnum.novice.value,
            0,
            100,
            10,
            10,
            10,
            0,
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
        role=safe_role,
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(int=10, dex=10, cha=10),
        badges=[],
        avatar_url=None,
        created_at=now,
        updated_at=now,
    )

    access_token = create_access_token(data={"sub": user_id})

    # Create refresh token and set it as httpOnly cookie
    try:
        refresh_token, expires_seconds = await create_refresh_token(user_id)
    except RefreshTokenStoreUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AUTH_SERVICE_UNAVAILABLE_DETAIL,
        ) from exc

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
    await check_rate_limit(get_client_ip(request), action="login", limit=60, window_seconds=300, request=request)
    await check_rate_limit(f"login_user:{credentials.username}", action="login_account", limit=30, window_seconds=900, request=request)

    # Accept email or username in the username field
    if "@" in credentials.username:
        _q_login = f"SELECT {_USER_AUTH_COLUMNS} FROM users WHERE email = $1"
    else:
        _q_login = f"SELECT {_USER_AUTH_COLUMNS} FROM users WHERE username = $1"
    with db_span("db.fetchrow", query="SELECT ... FROM users WHERE username/email = $1", params=[credentials.username]):
        user_row = await conn.fetchrow(_q_login, credentials.username)

    if not user_row:
        # Constant-time: prevent timing oracle revealing user existence
        verify_password("dummy_password", "$2b$12$LJ3m4ys3Lg3lE9Q8pBkSp.ZxOXSCmRCVHaLCQ5FhCjXxVx5m5sZ6C")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
        )
    if not verify_password(credentials.password, user_row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
        )

    if user_row["id"] == settings.PLATFORM_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account cannot log in",
        )

    # P1 A-01 FIX: Banned users must not log in
    if user_row.get("is_banned"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is banned",
        )

    user_profile = row_to_user_profile(user_row)

    access_token = create_access_token(data={"sub": user_row["id"]})

    # issue refresh token and set as httpOnly cookie
    try:
        refresh_token, expires_seconds = await create_refresh_token(user_row["id"])
    except RefreshTokenStoreUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AUTH_SERVICE_UNAVAILABLE_DETAIL,
        ) from exc

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
    await check_rate_limit(get_client_ip(request), action="logout", limit=10, window_seconds=60, request=request)
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        # P2-5 FIX: No cookie present — nothing to revoke, no-op
        return {"message": "Успешный выход"}
    try:
        await revoke_refresh_token(refresh)
    except RefreshTokenStoreUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AUTH_SERVICE_UNAVAILABLE_DETAIL,
        ) from exc
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
    await check_rate_limit(get_client_ip(request), action="refresh", limit=20, window_seconds=60, request=request)
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    try:
        user_id, new_refresh, expires_seconds = await rotate_refresh_token(refresh)
    except RefreshTokenStoreUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AUTH_SERVICE_UNAVAILABLE_DETAIL,
        ) from exc
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # load user profile
    _q_refresh = f"SELECT {_USER_SAFE_COLUMNS} FROM users WHERE id = $1"
    with db_span("db.fetchrow", query="SELECT ... FROM users WHERE id = $1", params=[user_id]):
        user_row = await conn.fetchrow(_q_refresh, user_id)
    if not user_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # P1-1 FIX: Banned users must not obtain new access tokens
    if user_row.get("is_banned"):
        await revoke_refresh_token(new_refresh)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is banned",
        )

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
