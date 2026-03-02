"""
Shared FastAPI dependencies — authentication & authorization.

Single source of truth for get_current_user / require_auth used
across all endpoint modules (quests, wallet, etc.).
"""

import ipaddress
import logging
from typing import Optional

import asyncpg
from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import settings
from app.core.otel_utils import db_span
from app.core.security import decode_access_token
from app.db.session import get_db_connection
from app.models.user import UserProfile, UserRoleEnum, row_to_user_profile

logger = logging.getLogger(__name__)


async def get_current_user(
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
    with db_span("db.fetchrow", query="SELECT * FROM users WHERE id = $1", params=[user_id]):
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    if row:
        user = row_to_user_profile(row)
        logger.debug(f"Authenticated: {user.username} ({user.id})")
        return user

    logger.warning(f"User not found for token sub: {user_id}")
    return None


async def require_auth(
    current_user: Optional[UserProfile] = Depends(get_current_user),
) -> UserProfile:
    """Dependency that requires a valid authenticated user. Raises 401 otherwise."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required",
        )
    return current_user


async def require_admin_role_only(
    current_user: UserProfile = Depends(require_auth),
) -> UserProfile:
    """Lightweight admin check — role only, no IP/TOTP.

    Used for TOTP setup/disable endpoints that must be reachable before
    the full ``require_admin`` gate is configured.
    """
    if current_user.role != UserRoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
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

    # ── IP allowlist ──────────────────────────────────────────────────────
    allowlist_raw = (settings.ADMIN_IP_ALLOWLIST or "").strip()
    if allowlist_raw:
        allowed = [ip.strip() for ip in allowlist_raw.split(",") if ip.strip()]
        client_ip_str = (request.client.host if request.client else "") or ""
        try:
            client_ip = ipaddress.ip_address(client_ip_str)
        except ValueError:
            client_ip = None

        ip_ok = False
        for entry in allowed:
            try:
                net = ipaddress.ip_network(entry, strict=False)
                if client_ip and client_ip in net:
                    ip_ok = True
                    break
            except ValueError:
                if entry == client_ip_str:
                    ip_ok = True
                    break

        if not ip_ok:
            logger.warning(
                f"Admin access denied for IP {client_ip_str} (user={current_user.id})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access not allowed from this IP address",
            )

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
        totp_secret = await conn.fetchval(
            "SELECT totp_secret FROM users WHERE id = $1", current_user.id
        )
        if not totp_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin 2FA not configured. Call POST /api/v1/admin/auth/totp/setup first.",
            )
        if not x_totp_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="X-TOTP-Token header required for admin access",
            )
        totp = pyotp.TOTP(totp_secret)
        if not totp.verify(x_totp_token, valid_window=1):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired TOTP token",
            )

    return current_user
