"""
Message service — chat within quests.

Only quest participants (client + assigned freelancer) can send/read messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

ALLOWED_CHAT_STATUSES = (
    "assigned",
    "in_progress",
    "completed",
    "revision_requested",
    "confirmed",
)


def _is_chat_schema_compat_error(exc: Exception) -> bool:
    return isinstance(exc, (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError, asyncpg.UndefinedFunctionError))


# ──────────────────────────────────────────
# Redis PubSub push helper
# ──────────────────────────────────────────

def _push_message_to_redis(msg_id: str, quest_id: str, author_id: str,
                           text: str, author_username: Optional[str],
                           now: "datetime") -> None:
    """Fire-and-forget publish to Redis channel chat:{quest_id}."""
    async def _publish() -> None:
        try:
            redis = await get_redis_client()
            if redis is None:
                return
            payload = json.dumps({
                "id": msg_id, "quest_id": quest_id,
                "author_id": author_id, "text": text,
                "author_username": author_username,
                "created_at": now.isoformat(),
                "message_type": "user",
            })
            await redis.publish(f"chat:{quest_id}", payload)
        except Exception:
            pass

    try:
        asyncio.get_running_loop()
        asyncio.create_task(_publish())
    except RuntimeError:
        pass


async def _touch_read_receipt(
    conn: asyncpg.Connection,
    quest_id: str,
    user_id: str,
    read_at: Optional[datetime] = None,
) -> None:
    read_at = read_at or datetime.now(timezone.utc)
    await conn.execute(
        """
        INSERT INTO quest_message_reads (quest_id, user_id, last_read_at)
        VALUES ($1, $2, $3)
        ON CONFLICT (quest_id, user_id)
        DO UPDATE SET last_read_at = EXCLUDED.last_read_at
        """,
        quest_id,
        user_id,
        read_at,
    )


async def create_system_message(
    conn: asyncpg.Connection,
    quest_id: str,
    text: str,
) -> dict:
    """Insert a system lifecycle message into the quest thread.

    Must be called inside an existing transaction (caller is responsible).
    """
    if conn.is_in_transaction() is False:
        raise RuntimeError("create_system_message must be called within a transaction")

    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO quest_messages (id, quest_id, author_id, text, created_at, message_type)
        VALUES ($1, $2, NULL, $3, $4, 'system')
        """,
        msg_id,
        quest_id,
        text.strip(),
        now,
    )

    return {
        "id": msg_id,
        "quest_id": quest_id,
        "author_id": None,
        "author_username": "Система",
        "text": text.strip(),
        "created_at": now.isoformat(),
        "message_type": "system",
    }


async def send_message(
    conn: asyncpg.Connection,
    quest_id: str,
    author_id: str,
    text: str,
) -> dict:
    """Send a message in a quest thread. Author must be a participant."""
    if not conn.is_in_transaction():
        raise RuntimeError("send_message must be called inside a DB transaction")

    # 1. Verify quest exists and get participants
    quest = await conn.fetchrow(
        "SELECT client_id, assigned_to, status FROM quests WHERE id = $1",
        quest_id,
    )
    if not quest:
        raise ValueError("Квест не найден")

    participants = {quest["client_id"], quest["assigned_to"]}
    if author_id not in participants:
        raise ValueError("Только участники квеста могут отправлять сообщения")

    if quest["status"] not in ALLOWED_CHAT_STATUSES:
        raise ValueError("Сообщения доступны только для квестов в работе/завершённых")

    # 2. Insert
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO quest_messages (id, quest_id, author_id, text, created_at, message_type)
        VALUES ($1, $2, $3, $4, $5, 'user')
        """,
        msg_id, quest_id, author_id, text.strip(), now,
    )

    # Get author username
    author_row = await conn.fetchrow("SELECT username FROM users WHERE id = $1", author_id)
    await _touch_read_receipt(conn, quest_id, author_id, now)

    author_username = author_row["username"] if author_row else None

    # Push to WS subscribers via Redis PubSub (best-effort, non-blocking)
    _push_message_to_redis(msg_id, quest_id, author_id, text.strip(), author_username, now)

    return {
        "id": msg_id,
        "quest_id": quest_id,
        "author_id": author_id,
        "author_username": author_username,
        "text": text.strip(),
        "created_at": now.isoformat(),
        "message_type": "user",
    }


async def get_messages(
    conn: asyncpg.Connection,
    quest_id: str,
    user_id: str,
    *,
    limit: int = 50,
    before: Optional[str] = None,
) -> dict:
    """Get messages for a quest thread. User must be a participant."""
    quest = await conn.fetchrow(
        "SELECT client_id, assigned_to FROM quests WHERE id = $1",
        quest_id,
    )
    if not quest:
        raise ValueError("Квест не найден")

    participants = {quest["client_id"], quest["assigned_to"]}
    if user_id not in participants:
        raise ValueError("Только участники квеста могут читать сообщения")

    try:
        unread_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM quest_messages m
            LEFT JOIN quest_message_reads r
                   ON r.quest_id = m.quest_id AND r.user_id = $2
            WHERE m.quest_id = $1
              AND m.created_at > COALESCE(r.last_read_at, TIMESTAMP 'epoch')
              AND COALESCE(m.author_id, '') <> $2
            """,
            quest_id,
            user_id,
        )

        query = """
            SELECT m.id, m.quest_id, m.author_id, u.username AS author_username,
                   m.text, m.created_at, m.message_type
            FROM quest_messages m
            LEFT JOIN users u ON u.id = m.author_id
            WHERE m.quest_id = $1
        """
        args: list = [quest_id]
        arg_idx = 2

        if before:
            query += f" AND m.created_at < ${arg_idx}::timestamptz"
            args.append(before)
            arg_idx += 1

        query += " ORDER BY m.created_at DESC"
        query += f" LIMIT ${arg_idx}"
        args.append(limit)

        rows = await conn.fetch(query, *args)
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM quest_messages WHERE quest_id = $1", quest_id
        )
    except Exception as exc:
        if not _is_chat_schema_compat_error(exc):
            raise
        logger.warning(
            "Falling back to compatibility mode for quest messages: quest=%s user=%s",
            quest_id,
            user_id,
            exc_info=True,
        )
        unread_count = 0
        fallback_query = """
            SELECT m.id, m.quest_id, m.author_id, u.username AS author_username,
                   m.text, m.created_at
            FROM quest_messages m
            LEFT JOIN users u ON u.id = m.author_id
            WHERE m.quest_id = $1
        """
        fallback_args: list = [quest_id]
        fallback_arg_idx = 2

        if before:
            fallback_query += f" AND m.created_at < ${fallback_arg_idx}::timestamptz"
            fallback_args.append(before)
            fallback_arg_idx += 1

        fallback_query += " ORDER BY m.created_at DESC"
        fallback_query += f" LIMIT ${fallback_arg_idx}"
        fallback_args.append(limit)

        rows = await conn.fetch(fallback_query, *fallback_args)
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM quest_messages WHERE quest_id = $1", quest_id
        )
    try:
        await _touch_read_receipt(conn, quest_id, user_id)
    except Exception:
        logger.warning("Read receipt update failed for quest %s user %s", quest_id, user_id, exc_info=True)

    messages = [
        {
            "id": row["id"],
            "quest_id": row["quest_id"],
            "author_id": row["author_id"],
            "author_username": row["author_username"] or "Система",
            "text": row["text"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "message_type": row["message_type"] or "user",
        }
        for row in reversed(rows)  # chronological order
    ]

    return {"messages": messages, "total": total or 0, "unread_count": int(unread_count or 0)}


async def list_dialogs(
    conn: asyncpg.Connection,
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List user's active quest dialogs with unread counters."""
    status_list = list(ALLOWED_CHAT_STATUSES)

    total = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM quests q
        WHERE (q.client_id = $1 OR q.assigned_to = $1)
          AND q.status::text = ANY($2::text[])
        """,
        user_id,
        status_list,
    )

    try:
        rows = await conn.fetch(
            """
            SELECT
                q.id AS quest_id,
                q.title AS quest_title,
                q.status AS quest_status,
                q.client_id,
                q.assigned_to,
                client.username AS client_username,
                freelancer.username AS freelancer_username,
                last_msg.text AS last_message_text,
                last_msg.message_type AS last_message_type,
                last_msg.created_at AS last_message_at,
                COALESCE(unread.cnt, 0) AS unread_count
            FROM quests q
            JOIN users client ON client.id = q.client_id
            LEFT JOIN users freelancer ON freelancer.id = q.assigned_to
            LEFT JOIN LATERAL (
                SELECT qm.text, qm.message_type, qm.created_at
                FROM quest_messages qm
                WHERE qm.quest_id = q.id
                ORDER BY qm.created_at DESC
                LIMIT 1
            ) last_msg ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS cnt
                FROM quest_messages qm
                LEFT JOIN quest_message_reads r
                       ON r.quest_id = q.id AND r.user_id = $1
                WHERE qm.quest_id = q.id
                  AND qm.created_at > COALESCE(r.last_read_at, TIMESTAMP 'epoch')
                  AND COALESCE(qm.author_id, '') <> $1
            ) unread ON TRUE
            WHERE (q.client_id = $1 OR q.assigned_to = $1)
              AND q.status::text = ANY($2::text[])
            ORDER BY COALESCE(last_msg.created_at, q.updated_at) DESC
            LIMIT $3 OFFSET $4
            """,
            user_id,
            status_list,
            limit,
            offset,
        )
    except Exception as exc:
        if not _is_chat_schema_compat_error(exc):
            raise
        logger.warning(
            "Falling back to compatibility mode for quest dialogs: user=%s",
            user_id,
            exc_info=True,
        )
        rows = await conn.fetch(
            """
            SELECT
                q.id AS quest_id,
                q.title AS quest_title,
                q.status AS quest_status,
                q.client_id,
                q.assigned_to,
                client.username AS client_username,
                freelancer.username AS freelancer_username,
                NULL::text AS last_message_text,
                NULL::text AS last_message_type,
                NULL::timestamptz AS last_message_at,
                0 AS unread_count
            FROM quests q
            JOIN users client ON client.id = q.client_id
            LEFT JOIN users freelancer ON freelancer.id = q.assigned_to
            WHERE (q.client_id = $1 OR q.assigned_to = $1)
              AND q.status::text = ANY($2::text[])
            ORDER BY q.updated_at DESC
            LIMIT $3 OFFSET $4
            """,
            user_id,
            status_list,
            limit,
            offset,
        )

    dialogs = []
    for row in rows:
        is_client = row["client_id"] == user_id
        dialogs.append(
            {
                "quest_id": row["quest_id"],
                "quest_title": row["quest_title"],
                "quest_status": row["quest_status"],
                "other_user_id": row["assigned_to"] if is_client else row["client_id"],
                "other_username": row["freelancer_username"] if is_client else row["client_username"],
                "last_message_text": row["last_message_text"],
                "last_message_type": row["last_message_type"] or "user",
                "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
                "unread_count": int(row["unread_count"] or 0),
            }
        )

    return {"dialogs": dialogs, "total": int(total or 0)}
