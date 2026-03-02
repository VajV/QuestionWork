"""
NotificationService — creates and reads user notifications.

Notifications are fire-and-forget: created inside an existing transaction
(so they roll back if the parent event fails).
"""

import logging
import uuid
from datetime import datetime, timezone

import asyncpg

from app.models.badge_notification import Notification, NotificationListResponse

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# Write (fire inside transactions)
# ──────────────────────────────────────────

async def create_notification(
    conn: asyncpg.Connection,
    user_id: str,
    title: str,
    message: str,
    event_type: str = "general",
) -> Notification:
    """Insert a notification row. Must be inside a DB transaction.

    Raises RuntimeError if conn is not in a transaction.
    """
    if not conn.is_in_transaction():
        raise RuntimeError(
            "create_notification must be called inside an explicit DB transaction."
        )

    notif_id = f"notif_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO notifications (id, user_id, title, message, event_type, is_read, created_at)
        VALUES ($1, $2, $3, $4, $5, FALSE, $6)
        """,
        notif_id,
        user_id,
        title,
        message,
        event_type,
        now,
    )

    logger.debug(f"Notification created: user={user_id}, type={event_type}, title={title!r}")

    return Notification(
        id=notif_id,
        user_id=user_id,
        title=title,
        message=message,
        event_type=event_type,
        is_read=False,
        created_at=now,
    )


# ──────────────────────────────────────────
# Read (no transaction required)
# ──────────────────────────────────────────

async def get_notifications(
    conn: asyncpg.Connection,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
) -> NotificationListResponse:
    """Return paginated notifications for a user, newest first."""
    base = "WHERE user_id = $1"
    args = [user_id]

    if unread_only:
        base += " AND is_read = FALSE"

    count = await conn.fetchval(
        f"SELECT COUNT(*) FROM notifications {base}", *args
    )
    unread_count = await conn.fetchval(
        "SELECT COUNT(*) FROM notifications WHERE user_id = $1 AND is_read = FALSE",
        user_id,
    )

    rows = await conn.fetch(
        f"""
        SELECT id, user_id, title, message, event_type, is_read, created_at
        FROM notifications {base}
        ORDER BY created_at DESC
        LIMIT ${ len(args)+1 } OFFSET ${ len(args)+2 }
        """,
        *args,
        limit,
        offset,
    )

    notifications = [
        Notification(
            id=r["id"],
            user_id=r["user_id"],
            title=r["title"],
            message=r["message"],
            event_type=r["event_type"],
            is_read=r["is_read"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

    return NotificationListResponse(
        notifications=notifications,
        total=int(count or 0),
        unread_count=int(unread_count or 0),
    )


async def mark_as_read(
    conn: asyncpg.Connection,
    notification_id: str,
    user_id: str,
) -> bool:
    """Mark a single notification as read. Only the owner can mark it.

    Returns True if updated, False if not found or not owned by user_id.
    """
    result = await conn.execute(
        """
        UPDATE notifications
        SET is_read = TRUE
        WHERE id = $1 AND user_id = $2 AND is_read = FALSE
        """,
        notification_id,
        user_id,
    )
    # asyncpg returns 'UPDATE N'
    return result.endswith("1")


async def mark_all_as_read(conn: asyncpg.Connection, user_id: str) -> int:
    """Mark ALL unread notifications for a user as read. Returns count updated."""
    result = await conn.execute(
        "UPDATE notifications SET is_read = TRUE WHERE user_id = $1 AND is_read = FALSE",
        user_id,
    )
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0
