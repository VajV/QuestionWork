"""Saved searches service — CRUD for user-defined search filters and alert subscriptions."""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

MAX_SAVED_SEARCHES_PER_USER = 20


async def list_saved_searches(
    conn: asyncpg.Connection, user_id: str
) -> List[asyncpg.Record]:
    """Return all saved searches for a user, newest first."""
    return await conn.fetch(
        """
        SELECT id, user_id, name, search_type, filters_json, alert_enabled,
               last_alerted_at, created_at
        FROM saved_searches
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )


async def create_saved_search(
    conn: asyncpg.Connection,
    user_id: str,
    *,
    name: Optional[str],
    search_type: str,
    filters_json: Dict[str, Any],
    alert_enabled: bool = False,
) -> asyncpg.Record:
    """Create a new saved search. Raises ValueError if limit exceeded."""
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM saved_searches WHERE user_id = $1", user_id
    )
    if (count or 0) >= MAX_SAVED_SEARCHES_PER_USER:
        raise ValueError(
            f"Saved search limit reached ({MAX_SAVED_SEARCHES_PER_USER} per user)"
        )

    row = await conn.fetchrow(
        """
        INSERT INTO saved_searches
            (user_id, name, search_type, filters_json, alert_enabled, created_at)
        VALUES ($1, $2, $3, $4::jsonb, $5, NOW())
        RETURNING id, user_id, name, search_type, filters_json, alert_enabled,
                  last_alerted_at, created_at
        """,
        user_id,
        name,
        search_type,
        json.dumps(filters_json),
        alert_enabled,
    )
    return row


async def delete_saved_search(
    conn: asyncpg.Connection, search_id: str, user_id: str
) -> bool:
    """Delete a saved search owned by user. Returns True if deleted."""
    result = await conn.execute(
        "DELETE FROM saved_searches WHERE id = $1::uuid AND user_id = $2",
        search_id,
        user_id,
    )
    return result.endswith("1")


async def get_alert_searches(
    conn: asyncpg.Connection,
) -> List[asyncpg.Record]:
    """Return all saved searches with alert_enabled=TRUE for the notification poller."""
    return await conn.fetch(
        """
        SELECT id, user_id, search_type, filters_json, last_alerted_at
        FROM saved_searches
        WHERE alert_enabled = TRUE
        ORDER BY last_alerted_at ASC NULLS FIRST
        """
    )


async def mark_alerted(conn: asyncpg.Connection, search_id: str) -> None:
    """Update last_alerted_at to now."""
    await conn.execute(
        "UPDATE saved_searches SET last_alerted_at = NOW() WHERE id = $1::uuid",
        search_id,
    )
