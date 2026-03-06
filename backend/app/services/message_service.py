"""
Message service — chat within quests.

Only quest participants (client + assigned freelancer) can send/read messages.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


async def send_message(
    conn: asyncpg.Connection,
    quest_id: str,
    author_id: str,
    text: str,
) -> dict:
    """Send a message in a quest thread. Author must be a participant."""
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

    if quest["status"] not in ("in_progress", "completed", "confirmed"):
        raise ValueError("Сообщения доступны только для квестов в работе/завершённых")

    # 2. Insert
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO quest_messages (id, quest_id, author_id, text, created_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        msg_id, quest_id, author_id, text.strip(), now,
    )

    # Get author username
    author_row = await conn.fetchrow("SELECT username FROM users WHERE id = $1", author_id)

    return {
        "id": msg_id,
        "quest_id": quest_id,
        "author_id": author_id,
        "author_username": author_row["username"] if author_row else None,
        "text": text.strip(),
        "created_at": now.isoformat(),
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

    query = """
        SELECT m.id, m.quest_id, m.author_id, u.username AS author_username,
               m.text, m.created_at
        FROM quest_messages m
        JOIN users u ON u.id = m.author_id
        WHERE m.quest_id = $1
    """
    args: list = [quest_id]
    arg_idx = 2

    if before:
        query += f" AND m.created_at < ${arg_idx}"
        args.append(before)
        arg_idx += 1

    query += " ORDER BY m.created_at DESC"
    query += f" LIMIT ${arg_idx}"
    args.append(limit)

    rows = await conn.fetch(query, *args)

    total = await conn.fetchval(
        "SELECT COUNT(*) FROM quest_messages WHERE quest_id = $1", quest_id
    )

    messages = [
        {
            "id": row["id"],
            "quest_id": row["quest_id"],
            "author_id": row["author_id"],
            "author_username": row["author_username"],
            "text": row["text"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in reversed(rows)  # chronological order
    ]

    return {"messages": messages, "total": total or 0}
