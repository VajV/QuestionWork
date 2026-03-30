"""Persistence helpers for worker and scheduler runtime heartbeats."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg


async def upsert_runtime_heartbeat(
    conn: asyncpg.Connection,
    *,
    runtime_kind: str,
    runtime_id: str,
    hostname: str,
    pid: int,
    started_at: datetime,
    last_seen_at: datetime,
    meta_json: dict[str, Any] | None = None,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        INSERT INTO runtime_heartbeats (
            runtime_kind, runtime_id, hostname, pid, started_at, last_seen_at, meta_json
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        ON CONFLICT (runtime_kind, runtime_id)
        DO UPDATE SET
            hostname = EXCLUDED.hostname,
            pid = EXCLUDED.pid,
            started_at = EXCLUDED.started_at,
            last_seen_at = EXCLUDED.last_seen_at,
            meta_json = EXCLUDED.meta_json
        RETURNING *
        """,
        runtime_kind,
        runtime_id,
        hostname,
        pid,
        started_at,
        last_seen_at,
        json.dumps(meta_json or {}),
    )


async def get_runtime_heartbeat(
    conn: asyncpg.Connection,
    *,
    runtime_kind: str,
    runtime_id: str,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT * FROM runtime_heartbeats WHERE runtime_kind = $1 AND runtime_id = $2",
        runtime_kind,
        runtime_id,
    )


async def find_stale_runtimes(
    conn: asyncpg.Connection,
    *,
    runtime_kind: str,
    stale_before: datetime,
    limit: int = 100,
) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT *
        FROM runtime_heartbeats
        WHERE runtime_kind = $1
          AND last_seen_at < $2
        ORDER BY last_seen_at ASC
        LIMIT $3
        """,
        runtime_kind,
        stale_before,
        limit,
    )


async def delete_stale_runtimes(
    conn: asyncpg.Connection,
    *,
    stale_before: datetime,
    runtime_kind: str | None = None,
) -> int:
    if runtime_kind is None:
        deleted = await conn.fetchval(
            """
            WITH deleted AS (
                DELETE FROM runtime_heartbeats
                WHERE last_seen_at < $1
                RETURNING 1
            )
            SELECT COUNT(*)::int FROM deleted
            """,
            stale_before,
        )
        return int(deleted or 0)

    deleted = await conn.fetchval(
        """
        WITH deleted AS (
            DELETE FROM runtime_heartbeats
            WHERE runtime_kind = $1
              AND last_seen_at < $2
            RETURNING 1
        )
        SELECT COUNT(*)::int FROM deleted
        """,
        runtime_kind,
        stale_before,
    )
    return int(deleted or 0)