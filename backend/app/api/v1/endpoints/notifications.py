"""
Notifications endpoints.

GET  /notifications              — list (newest first, paginated, optional unread_only)
PATCH /notifications/{id}/read   — mark one as read
POST /notifications/read-all     — mark all as read
"""

import logging
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_auth
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", summary="List notifications for the authenticated user")
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return paginated notifications, newest first.

    Pass ``unread_only=true`` to fetch only unread ones.
    Response includes ``unread_count`` for badge display.
    """
    return await notification_service.get_notifications(
        conn,
        current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )


@router.patch("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Mark a single notification as read. Returns 404 if not found or not owned."""
    updated = await notification_service.mark_as_read(conn, notification_id, current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or already read",
        )
    return {"id": notification_id, "is_read": True}


@router.post("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Mark all unread notifications as read for the authenticated user."""
    count = await notification_service.mark_all_as_read(conn, current_user.id)
    return {"marked_read": count}
