"""Service layer for first-party analytics event ingestion and KPI queries."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


# ── Write ────────────────────────────────────────────────────────────────────


async def ingest_event(
    conn: asyncpg.Connection,
    *,
    event_name: str,
    user_id: Optional[str],
    session_id: Optional[str],
    role: Optional[str],
    source: Optional[str],
    path: Optional[str],
    properties: Dict[str, Any],
    occurred_at: Optional[datetime] = None,
) -> None:
    """Insert a single analytics event row."""
    now = occurred_at or datetime.now(timezone.utc)
    await conn.execute(
        """
        INSERT INTO analytics_events
            (event_name, user_id, session_id, role, source, path, properties_json, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
        """,
        event_name,
        user_id,
        session_id,
        role,
        source,
        path,
        json.dumps(properties),
        now,
    )


async def ingest_events_batch(
    conn: asyncpg.Connection,
    *,
    user_id: Optional[str],
    events: List[Dict[str, Any]],
) -> int:
    """Insert a batch of events. Returns count successfully inserted."""
    count = 0
    for ev in events:
        try:
            occurred_at = ev.get("timestamp")
            if isinstance(occurred_at, str):
                try:
                    occurred_at = datetime.fromisoformat(occurred_at)
                except ValueError:
                    occurred_at = None

            await ingest_event(
                conn,
                event_name=ev["event_name"],
                user_id=user_id,
                session_id=ev.get("session_id"),
                role=ev.get("role"),
                source=ev.get("source"),
                path=ev.get("path"),
                properties=ev.get("properties", {}),
                occurred_at=occurred_at,
            )
            count += 1
        except Exception as exc:
            logger.warning(
                "Failed to ingest analytics event %r: %s",
                ev.get("event_name"),
                exc,
            )
    return count


async def prune_old_events(conn: asyncpg.Connection, retention_days: int) -> int:
    """Delete analytics events older than the configured retention window."""
    deleted_count = await conn.fetchval(
        """
        WITH deleted AS (
            DELETE FROM analytics_events
            WHERE created_at < NOW() - ($1::text || ' days')::interval
            RETURNING 1
        )
        SELECT COUNT(*)::INT FROM deleted
        """,
        retention_days,
    )
    return int(deleted_count or 0)


# ── Funnel KPI queries ────────────────────────────────────────────────────────


async def get_funnel_kpis(conn: asyncpg.Connection) -> Dict[str, Any]:
    """Return funnel KPI counts for the admin growth dashboard.

    Counts are all-time totals. Each step is independent to keep queries cheap.
    """
    rows = await conn.fetch(
        """
        SELECT
            -- Client funnel
            (SELECT COUNT(DISTINCT user_id) FROM analytics_events
             WHERE event_name = 'landing_view') AS landing_views,
            (SELECT COUNT(DISTINCT user_id) FROM analytics_events
             WHERE event_name = 'register_started') AS register_started,
            (SELECT COUNT(*) FROM users
             WHERE role = 'client') AS clients_registered,
            (SELECT COUNT(DISTINCT client_id) FROM quests) AS clients_with_quests,
            (SELECT COUNT(*) FROM quests) AS quests_created,
            (SELECT COUNT(*) FROM applications) AS applications_submitted,
            (SELECT COUNT(*) FROM quests
             WHERE status IN ('assigned','in_progress','completed','confirmed')) AS hires,
            (SELECT COUNT(*) FROM quests
             WHERE status = 'confirmed') AS confirmed_completions,
            -- Repeat hire proxy: clients with more than 1 confirmed quest
            (SELECT COUNT(*) FROM (
                SELECT client_id FROM quests
                WHERE status = 'confirmed'
                GROUP BY client_id
                HAVING COUNT(*) > 1
            ) sub) AS clients_with_repeat_hire
        """
    )
    row = rows[0] if rows else {}
    return {
        "landing_views": int(row.get("landing_views") or 0),
        "register_started": int(row.get("register_started") or 0),
        "clients_registered": int(row.get("clients_registered") or 0),
        "clients_with_quests": int(row.get("clients_with_quests") or 0),
        "quests_created": int(row.get("quests_created") or 0),
        "applications_submitted": int(row.get("applications_submitted") or 0),
        "hires": int(row.get("hires") or 0),
        "confirmed_completions": int(row.get("confirmed_completions") or 0),
        "clients_with_repeat_hire": int(row.get("clients_with_repeat_hire") or 0),
    }
