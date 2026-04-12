"""
NotificationService — creates and reads user notifications.

Notifications are fire-and-forget: created inside an existing transaction
(so they roll back if the parent event fails).
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.core.redis_client import get_redis_client
from app.models.badge_notification import Notification, NotificationListResponse

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# Redis PubSub push helper
# ──────────────────────────────────────────

def _push_notification_to_redis(
    notif_id: str, user_id: str, title: str, message: str,
    event_type: str, now: "datetime",
) -> None:
    """Fire-and-forget publish to Redis channel notifications:{user_id}.

    Uses asyncio.create_task so Redis failure never breaks the DB transaction.
    """
    async def _publish() -> None:
        try:
            redis = await get_redis_client()
            if redis is None:
                return
            payload = json.dumps({
                "id": notif_id, "user_id": user_id,
                "title": title, "message": message,
                "event_type": event_type, "is_read": False,
                "created_at": now.isoformat(),
            })
            await redis.publish(f"notifications:{user_id}", payload)
        except Exception:
            pass  # WS push is best-effort

    try:
        asyncio.get_running_loop()
        asyncio.create_task(_publish())
    except RuntimeError:
        pass  # no running loop (e.g. in tests)


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

    # Push to WS subscribers via Redis PubSub (best-effort, non-blocking)
    _push_notification_to_redis(notif_id, user_id, title, message, event_type, now)

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
    cursor: Optional[str] = None,
) -> NotificationListResponse:
    """Return paginated notifications for a user, newest first.

    Supports cursor-based pagination (preferred) and legacy offset.
    When ``cursor`` is provided it takes precedence over ``offset``.
    """
    # ── M-02: single query for both total and unread counts ──────────
    if unread_only:
        counts = await conn.fetchrow(
            "SELECT COUNT(*) AS total FROM notifications WHERE user_id = $1 AND is_read = FALSE",
            user_id,
        )
        total = int(counts["total"] or 0)
        unread_count = total
    else:
        counts = await conn.fetchrow(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE is_read = FALSE) AS unread_count
            FROM notifications
            WHERE user_id = $1
            """,
            user_id,
        )
        total = int(counts["total"] or 0)
        unread_count = int(counts["unread_count"] or 0)

    # ── M-03: cursor-based pagination (falls back to OFFSET) ─────────
    base_filter = "WHERE user_id = $1"
    if unread_only:
        base_filter += " AND is_read = FALSE"

    if cursor:
        # Look up the cursor notification's created_at
        cursor_row = await conn.fetchrow(
            "SELECT created_at FROM notifications WHERE id = $1 AND user_id = $2",
            cursor,
            user_id,
        )
        if cursor_row:
            rows = await conn.fetch(
                f"""
                SELECT id, user_id, title, message, event_type, is_read, created_at
                FROM notifications {base_filter}
                  AND (created_at, id) < ($2, $3)
                ORDER BY created_at DESC, id DESC
                LIMIT $4
                """,
                user_id,
                cursor_row["created_at"],
                cursor,
                limit,
            )
        else:
            rows = []
    else:
        args = [user_id]
        rows = await conn.fetch(
            f"""
            SELECT id, user_id, title, message, event_type, is_read, created_at
            FROM notifications {base_filter}
            ORDER BY created_at DESC, id DESC
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
        total=total,
        unread_count=unread_count,
        next_cursor=notifications[-1].id if notifications else None,
    )


async def mark_as_read(
    conn: asyncpg.Connection,
    notification_id: str,
    user_id: str,
) -> bool:
    """Mark a single notification as read. Only the owner can mark it.

    Returns True if updated, False if not found or not owned by user_id.
    """
    if not conn.is_in_transaction():
        raise RuntimeError(
            "mark_as_read must be called inside an explicit DB transaction."
        )
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
    if not conn.is_in_transaction():
        raise RuntimeError(
            "mark_all_as_read must be called inside an explicit DB transaction."
        )
    result = await conn.execute(
        "UPDATE notifications SET is_read = TRUE WHERE user_id = $1 AND is_read = FALSE",
        user_id,
    )
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0


# ── Notification preferences ──────────────────────────────────────────────────


async def get_preferences(conn: asyncpg.Connection, user_id: str) -> dict:
    """Return the notification preferences for a user, creating defaults if absent."""
    row = await conn.fetchrow(
        "SELECT transactional_enabled, growth_enabled, digest_enabled FROM notification_preferences WHERE user_id = $1",
        user_id,
    )
    if row:
        return dict(row)
    return {"transactional_enabled": True, "growth_enabled": True, "digest_enabled": True}


async def update_preferences(
    conn: asyncpg.Connection,
    user_id: str,
    *,
    transactional_enabled: bool,
    growth_enabled: bool,
    digest_enabled: bool,
) -> dict:
    """Upsert notification preferences for a user."""
    await conn.execute(
        """
        INSERT INTO notification_preferences
            (user_id, transactional_enabled, growth_enabled, digest_enabled, updated_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (user_id) DO UPDATE
            SET transactional_enabled = EXCLUDED.transactional_enabled,
                growth_enabled        = EXCLUDED.growth_enabled,
                digest_enabled        = EXCLUDED.digest_enabled,
                updated_at            = NOW()
        """,
        user_id,
        transactional_enabled,
        growth_enabled,
        digest_enabled,
    )
    return {
        "transactional_enabled": transactional_enabled,
        "growth_enabled": growth_enabled,
        "digest_enabled": digest_enabled,
    }
