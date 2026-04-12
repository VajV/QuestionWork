"""
Notifications endpoints.

GET  /notifications              — list (newest first, paginated, optional unread_only)
PATCH /notifications/{id}/read   — mark one as read
POST /notifications/read-all     — mark all as read
"""

import logging
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.realtime import WebSocketTicketResponse
from app.models.user import UserProfile
from app.services import notification_service, realtime_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", summary="List notifications for the authenticated user")
async def list_notifications(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    cursor: str = Query(default=None, description="Notification ID for cursor-based pagination"),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return paginated notifications, newest first.

    Pass ``unread_only=true`` to fetch only unread ones.
    Pass ``cursor`` (notification ID) for cursor-based pagination.
    Response includes ``unread_count`` for badge display.
    """
    await check_rate_limit(get_client_ip(request), action="list_notifications", limit=60, window_seconds=60)
    return await notification_service.get_notifications(
        conn,
        current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        cursor=cursor,
    )


@router.patch("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Mark a single notification as read. Returns 404 if not found or not owned."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="mark_notification_read", limit=60, window_seconds=60)
    async with conn.transaction():
        updated = await notification_service.mark_as_read(conn, notification_id, current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or already read",
        )
    return {"id": notification_id, "is_read": True}


@router.post("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Mark all unread notifications as read for the authenticated user."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="mark_all_notifications_read", limit=20, window_seconds=60)
    async with conn.transaction():
        count = await notification_service.mark_all_as_read(conn, current_user.id)
    return {"marked_read": count}


@router.post("/ws-ticket", response_model=WebSocketTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_notifications_ws_ticket(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
):
    """Issue a short-lived WebSocket ticket for notification push auth."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="issue_notifications_ws_ticket", limit=30, window_seconds=60)
    return WebSocketTicketResponse(**await realtime_service.issue_notifications_ticket(current_user.id))


# ── Notification preferences ──────────────────────────────────────────────────


class NotificationPreferencesBody(BaseModel):
    transactional_enabled: bool = True
    growth_enabled: bool = True
    digest_enabled: bool = True


@router.get("/preferences", status_code=status.HTTP_200_OK)
async def get_notification_preferences(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return the current user's notification channel preferences."""
    await check_rate_limit(get_client_ip(request), action="get_notification_prefs", limit=30, window_seconds=60)
    return await notification_service.get_preferences(conn, current_user.id)


@router.put("/preferences", status_code=status.HTTP_200_OK)
async def update_notification_preferences(
    body: NotificationPreferencesBody,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Update the current user's notification channel preferences."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="update_notification_prefs", limit=20, window_seconds=60)
    return await notification_service.update_preferences(
        conn,
        current_user.id,
        transactional_enabled=body.transactional_enabled,
        growth_enabled=body.growth_enabled,
        digest_enabled=body.digest_enabled,
    )
