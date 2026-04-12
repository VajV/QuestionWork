"""Saved searches service — CRUD for user-defined search filters and alert subscriptions."""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

MAX_SAVED_SEARCHES_PER_USER = 20

# A saved search alert is considered "stale" if we last alerted less than
# this many seconds ago.  Prevents excessive notifications on noisy markets.
ALERT_COOLDOWN_SECONDS = 1800  # 30 minutes per-search


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
    async with conn.transaction():
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


async def count_new_quests_for_filters(
    conn: asyncpg.Connection,
    *,
    filters: Dict[str, Any],
    since: Optional[datetime],
) -> int:
    """Count open quests posted after *since* that match the saved search filters.

    Used to decide whether to fire an alert notification.  Conservatively
    returns 0 on any unknown filter key so we never alert spuriously.
    """
    conditions = ["status = 'open'"]
    params: list[Any] = []

    if since is not None:
        params.append(since)
        conditions.append(f"created_at > ${len(params)}")

    grade = filters.get("grade") or filters.get("grade_filter")
    if grade:
        params.append(grade)
        conditions.append(f"grade = ${len(params)}")

    min_budget = filters.get("min_budget")
    if min_budget is not None:
        try:
            params.append(float(min_budget))
            conditions.append(f"budget >= ${len(params)}")
        except (TypeError, ValueError):
            pass

    max_budget = filters.get("max_budget")
    if max_budget is not None:
        try:
            params.append(float(max_budget))
            conditions.append(f"budget <= ${len(params)}")
        except (TypeError, ValueError):
            pass

    skill = filters.get("skill") or filters.get("skill_filter")
    if skill:
        params.append(f"%{skill}%")
        conditions.append(f"(title ILIKE ${len(params)} OR description ILIKE ${len(params)})")

    where = " AND ".join(conditions) or "TRUE"
    sql = f"SELECT COUNT(*) FROM quests WHERE {where}"
    count = await conn.fetchval(sql, *params)
    return int(count or 0)


async def run_alert_scan(
    conn: asyncpg.Connection,
    *,
    batch_limit: int = 50,
) -> int:
    """Evaluate saved searches with alerts enabled and emit notifications.

    Processes up to *batch_limit* searches per call, ordered by least-recently-
    alerted so no search is perpetually skipped.  Returns the number of alerts
    actually sent.
    """
    from app.services import notification_service  # local import to avoid circular

    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(seconds=ALERT_COOLDOWN_SECONDS)
    rows = await conn.fetch(
        """
        SELECT id, user_id, name, search_type, filters_json, last_alerted_at
        FROM saved_searches
        WHERE alert_enabled = TRUE
          AND (last_alerted_at IS NULL OR last_alerted_at < $1)
        ORDER BY last_alerted_at ASC NULLS FIRST
        LIMIT $2
        """,
        cooldown_cutoff,
        batch_limit,
    )

    alerts_sent = 0
    for row in rows:
        try:
            filters = json.loads(row["filters_json"]) if row["filters_json"] else {}
            since = row["last_alerted_at"]
            count = await count_new_quests_for_filters(conn, filters=filters, since=since)
            if count == 0:
                continue

            search_name = row["name"] or "Сохранённый поиск"
            title = f"🔔 Новые квесты по поиску «{search_name}»"
            message = (
                f"Появилось {count} нов{'ый' if count == 1 else 'ых'} "
                f"квест{'а' if 1 < count < 5 else 'ов' if count % 10 in {5,6,7,8,9,0} else ''} "
                f"по вашему сохранённому поиску."
            )

            async with conn.transaction():
                await notification_service.create_notification(
                    conn,
                    row["user_id"],
                    title,
                    message,
                    event_type="saved_search_alert",
                )
                await mark_alerted(conn, str(row["id"]))

            alerts_sent += 1
        except Exception:
            logger.exception("Saved search alert failed for search_id=%s", row["id"])

    return alerts_sent
