"""Shared quest helpers used by both quest_service and admin_service.

Extracted to avoid code duplication of status history recording logic.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg


async def record_quest_status_history(
    conn: asyncpg.Connection,
    quest_id: str,
    from_status: Optional[str],
    to_status: str,
    *,
    changed_by: Optional[str] = None,
    note: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> None:
    """Insert a quest status transition record into quest_status_history."""
    history_id = f"qsh_{uuid.uuid4().hex[:12]}"
    ts = created_at or datetime.now(timezone.utc)
    await conn.execute(
        """
        INSERT INTO quest_status_history (
            id, quest_id, from_status, to_status, changed_by, note, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        history_id,
        quest_id,
        from_status,
        to_status,
        changed_by,
        note,
        ts,
    )
