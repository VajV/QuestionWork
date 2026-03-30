"""
Badges endpoints.

GET /badges/catalogue   — full badge catalogue (public)
GET /badges/me          — badges earned by the authenticated user
GET /badges/{user_id}   — badges earned by any user (public profile)
"""

import logging
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import badge_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/badges", tags=["Badges"])


async def _badge_read_rate_limit(request: Request) -> None:
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="badge_read", limit=60, window_seconds=60)


@router.get("/catalogue", summary="List all available badges")
async def get_badge_catalogue(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Public endpoint — returns the full badge catalogue with criteria."""
    await _badge_read_rate_limit(request)
    return {"badges": await badge_service.get_badge_catalogue(conn)}


@router.get("/me", summary="Badges earned by the authenticated user")
async def get_my_badges(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return all badges earned by the logged-in user."""
    await _badge_read_rate_limit(request)
    earned = await badge_service.get_user_badges(conn, current_user.id)
    return {"user_id": current_user.id, "badges": earned, "total": len(earned)}


@router.get("/{user_id}", summary="Badges earned by a specific user")
async def get_user_badges(
    user_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return all badges earned by the given user (public profile view)."""
    await _badge_read_rate_limit(request)
    # Verify user exists
    exists = await conn.fetchval("SELECT 1 FROM users WHERE id = $1", user_id)
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    earned = await badge_service.get_user_badges(conn, user_id)
    return {"user_id": user_id, "badges": earned, "total": len(earned)}
