"""Persistence helpers for command_requests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg


async def create_command(
    conn: asyncpg.Connection,
    *,
    command_kind: str,
    status: str = "accepted",
    dedupe_key: str | None = None,
    requested_by_user_id: str | None = None,
    requested_by_admin_id: str | None = None,
    request_ip: str | None = None,
    request_user_agent: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    payload_json: dict[str, Any] | None = None,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        INSERT INTO command_requests (
            command_kind, status, dedupe_key,
            requested_by_user_id, requested_by_admin_id,
            request_ip, request_user_agent, request_id, trace_id,
            payload_json
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
        RETURNING *
        """,
        command_kind,
        status,
        dedupe_key,
        requested_by_user_id,
        requested_by_admin_id,
        request_ip,
        request_user_agent,
        request_id,
        trace_id,
        json.dumps(payload_json or {}),
    )


async def get_command_by_id(conn: asyncpg.Connection, command_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM command_requests WHERE id = $1", command_id)


async def find_replayable_command_by_dedupe_key(
    conn: asyncpg.Connection,
    *,
    command_kind: str,
    dedupe_key: str,
    replay_window_seconds: int = 24 * 60 * 60,
    now: datetime | None = None,
) -> asyncpg.Record | None:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(seconds=replay_window_seconds)
    return await conn.fetchrow(
        """
        SELECT *
        FROM command_requests
        WHERE command_kind = $1
          AND dedupe_key = $2
          AND status IN ('accepted', 'running', 'succeeded')
          AND submitted_at >= $3
        ORDER BY submitted_at DESC
        LIMIT 1
        """,
        command_kind,
        dedupe_key,
        cutoff,
    )


async def mark_command_running(conn: asyncpg.Connection, command_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE command_requests
        SET status = 'running', started_at = COALESCE(started_at, NOW()), updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        command_id,
    )


async def mark_command_succeeded(
    conn: asyncpg.Connection,
    command_id: str,
    *,
    result_json: dict[str, Any] | None = None,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE command_requests
        SET status = 'succeeded',
            result_json = $2::jsonb,
            finished_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        command_id,
        json.dumps(result_json or {}),
    )


async def mark_command_failed(
    conn: asyncpg.Connection,
    command_id: str,
    *,
    error_code: str | None = None,
    error_text: str | None = None,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE command_requests
        SET status = 'failed',
            error_code = $2,
            error_text = $3,
            finished_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        command_id,
        error_code,
        error_text,
    )


async def mark_command_cancelled(conn: asyncpg.Connection, command_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE command_requests
        SET status = 'cancelled', finished_at = NOW(), updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        command_id,
    )