"""Shared FastAPI dependencies — authentication & authorization."""

import logging
import time
from collections import OrderedDict
from typing import Optional

import asyncpg
from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import settings
from app.core.otel_utils import db_span
from app.core.ratelimit import get_admin_request_ip, ip_matches_allowlist
from app.core.redis_client import get_redis_client
from app.core.security import decode_access_token, decrypt_totp_secret
from app.db.session import get_db_connection
from app.models.user import UserProfile, UserRoleEnum, row_to_user_profile

logger = logging.getLogger(__name__)

# Explicit column list for user queries — never use SELECT *
# This excludes: password_hash, totp_secret, pending_totp_secret
_USER_SAFE_COLUMNS = (
    "id, username, email, role, is_banned, banned_reason, "
    "level, grade, xp, xp_to_next, stat_points, "
    "stats_int, stats_dex, stats_cha, badges, bio, avatar_url, skills, "
    "availability_status, portfolio_links, portfolio_summary, "
    "onboarding_completed, onboarding_completed_at, profile_completeness_percent, "
    "character_class, "
    "created_at, updated_at"
)

# ── P1 A-03: In-memory TOTP replay store (fallback when Redis is down) ──
_TOTP_REPLAY_STORE: OrderedDict[str, float] = OrderedDict()
_TOTP_REPLAY_TTL = 90  # seconds (matches valid_window=1, i.e. 3×30s = 90s window)
_TOTP_REPLAY_MAX_KEYS = 5000


def _totp_replay_check_memory(user_id: str, token: str) -> None:
    """Check/store TOTP token in memory. Raises HTTPException on replay."""
    now = time.time()
    key = f"{user_id}:{token}"

    # Evict expired entries
    while _TOTP_REPLAY_STORE:
        oldest_key, oldest_time = next(iter(_TOTP_REPLAY_STORE.items()))
        if now - oldest_time > _TOTP_REPLAY_TTL:
            _TOTP_REPLAY_STORE.pop(oldest_key)
        else:
            break

    # Cap size
    while len(_TOTP_REPLAY_STORE) >= _TOTP_REPLAY_MAX_KEYS:
        _TOTP_REPLAY_STORE.popitem(last=False)

    if key in _TOTP_REPLAY_STORE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TOTP token already used. Wait for the next code.",
        )
    _TOTP_REPLAY_STORE[key] = now


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> Optional[UserProfile]:
    """Extract the current user from the Bearer token. Returns None if not authenticated."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)

    if not payload:
        return None

    user_id = payload.get("sub")
    _q = f"SELECT {_USER_SAFE_COLUMNS} FROM users WHERE id = $1"
    with db_span("db.fetchrow", query=_q, params=[user_id]):
        row = await conn.fetchrow(_q, user_id)

    if row:
        # Check ban status
        if row.get("is_banned"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is banned",
            )
        user = row_to_user_profile(row)
        logger.debug("Authenticated: user=%s", user.id[:8])
        return user

    logger.warning("User not found for token sub: %s", user_id[:8] if user_id else "?")
    return None


async def require_auth(
    current_user: Optional[UserProfile] = Depends(get_optional_user),
) -> UserProfile:
    """Dependency that requires a valid authenticated user. Raises 401 otherwise."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required",
        )
    return current_user


# Fail-closed alias: any new code using get_current_user gets the strict version.
get_current_user = require_auth


async def require_admin_role_only(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
) -> UserProfile:
    """Admin check with role + IP allowlist, but no TOTP.

    Used for TOTP setup/disable endpoints that must be reachable before
    TOTP is configured, but should still respect IP restrictions.
    """
    if current_user.role != UserRoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    _enforce_admin_ip_allowlist(request, current_user.id, action_name="Admin TOTP setup")
    return current_user


async def require_admin(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
    x_totp_token: Optional[str] = Header(None, alias="X-TOTP-Token"),
) -> UserProfile:
    """Dependency that requires admin role, IP allowlist, and optional TOTP."""
    if current_user.role != UserRoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    _enforce_admin_ip_allowlist(request, current_user.id, action_name="Admin access")

    # ── TOTP verification ─────────────────────────────────────────────────
    if settings.ADMIN_TOTP_REQUIRED:
        try:
            import pyotp  # lazy import — only needed when TOTP is enabled
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="TOTP required but pyotp is not installed",
            )

        # Fetch totp_secret straight from DB (authoritative, not cached in JWT)
        totp_secret_encrypted = await conn.fetchval(
            "SELECT totp_secret FROM users WHERE id = $1", current_user.id
        )
        if not totp_secret_encrypted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin 2FA not configured. Call POST /api/v1/admin/auth/totp/setup first.",
            )
        if not x_totp_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="X-TOTP-Token header required for admin access",
            )
        totp_secret = decrypt_totp_secret(totp_secret_encrypted)
        totp = pyotp.TOTP(totp_secret)
        if not totp.verify(x_totp_token, valid_window=1):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired TOTP token",
            )

        # TOTP replay protection: reject codes already used within the window
        requires_redis = settings.APP_ENV.lower() not in {"local", "test", "dev", "development"}
        try:
            redis = await get_redis_client(required_in_production=requires_redis)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Redis is required for admin TOTP replay protection in this environment. "
                    "Check REDIS_URL and ensure Redis is running."
                ),
            ) from exc

        if redis is None and requires_redis:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Redis is required for admin TOTP replay protection in this environment. "
                    "Check REDIS_URL and ensure Redis is running."
                ),
            )

        if redis is not None:
            replay_key = f"totp_used:{current_user.id}:{x_totp_token}"
            if await redis.get(replay_key):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="TOTP token already used. Wait for the next code.",
                )
            await redis.setex(replay_key, 90, "1")  # 90s covers valid_window=1 (3x30s window)
        else:
            _totp_replay_check_memory(current_user.id, x_totp_token)

    return current_user


def _enforce_admin_ip_allowlist(request: Request, user_id: str, *, action_name: str) -> None:
    allowlist_raw = (settings.ADMIN_IP_ALLOWLIST or "").strip()
    if not allowlist_raw:
        return

    client_ip_str = get_admin_request_ip(request)
    if ip_matches_allowlist(client_ip_str, allowlist_raw):
        return

    logger.warning("%s denied for IP %s (user=%s)", action_name, client_ip_str, user_id[:8] if user_id else "?")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access not allowed from this IP address",
    )
