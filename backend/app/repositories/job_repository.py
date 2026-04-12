"""Persistence helpers for background_jobs and background_job_attempts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import asyncpg


async def create_job(
    conn: asyncpg.Connection,
    *,
    kind: str,
    status: str = "queued",
    queue_name: str = "default",
    priority: int = 100,
    dedupe_key: str | None = None,
    payload_json: dict[str, Any] | None = None,
    scheduled_for: datetime | None = None,
    available_at: datetime | None = None,
    max_attempts: int = 5,
    trace_id: str | None = None,
    request_id: str | None = None,
    created_by_user_id: str | None = None,
    created_by_admin_id: str | None = None,
    command_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> asyncpg.Record:
    now = datetime.now(timezone.utc)
    scheduled = scheduled_for or now
    available = available_at or scheduled
    return await conn.fetchrow(
        """
        INSERT INTO background_jobs (
            kind, queue_name, status, priority, dedupe_key,
            payload_json, scheduled_for, available_at, max_attempts,
            trace_id, request_id, created_by_user_id, created_by_admin_id,
            command_id, entity_type, entity_id
        )
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        RETURNING *
        """,
        kind,
        queue_name,
        status,
        priority,
        dedupe_key,
        json.dumps(payload_json or {}),
        scheduled,
        available,
        max_attempts,
        trace_id,
        request_id,
        created_by_user_id,
        created_by_admin_id,
        command_id,
        entity_type,
        entity_id,
    )


async def get_job_by_id(conn: asyncpg.Connection, job_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM background_jobs WHERE id = $1", job_id)


async def claim_job(
    conn: asyncpg.Connection,
    *,
    job_id: str,
    worker_id: str,
    lock_token: str,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE background_jobs
        SET status = 'running',
            lock_token = $3,
            locked_by = $2,
            started_at = COALESCE(started_at, NOW()),
            last_heartbeat_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
          AND status IN ('queued', 'retry_scheduled')
        RETURNING *
        """,
        job_id,
        worker_id,
        lock_token,
    )


async def insert_attempt(
    conn: asyncpg.Connection,
    *,
    job_id: str,
    attempt_no: int,
    worker_id: str,
    started_at: datetime,
    status: str = "running",
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        INSERT INTO background_job_attempts (job_id, attempt_no, worker_id, started_at, status)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        job_id,
        attempt_no,
        worker_id,
        started_at,
        status,
    )


async def mark_job_succeeded(
    conn: asyncpg.Connection,
    job_id: str,
    *,
    finished_at: datetime | None = None,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE background_jobs
        SET status = 'succeeded', finished_at = COALESCE($2, NOW()), updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        job_id,
        finished_at,
    )


async def mark_job_retry_scheduled(
    conn: asyncpg.Connection,
    job_id: str,
    *,
    error_code: str | None,
    error_text: str | None,
    available_at: datetime,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE background_jobs
        SET status = 'retry_scheduled',
            last_error_code = $2,
            last_error = $3,
            attempt_count = attempt_count + 1,
            available_at = $4,
            lock_token = NULL,
            locked_by = NULL,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        job_id,
        error_code,
        error_text,
        available_at,
    )


async def mark_job_failed(
    conn: asyncpg.Connection,
    job_id: str,
    *,
    error_code: str | None,
    error_text: str | None,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE background_jobs
        SET status = 'failed',
            last_error_code = $2,
            last_error = $3,
            attempt_count = attempt_count + 1,
            finished_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        job_id,
        error_code,
        error_text,
    )


async def mark_job_dead_letter(
    conn: asyncpg.Connection,
    job_id: str,
    *,
    error_code: str | None,
    error_text: str | None,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE background_jobs
        SET status = 'dead_letter',
            last_error_code = $2,
            last_error = $3,
            attempt_count = attempt_count + 1,
            finished_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        job_id,
        error_code,
        error_text,
    )


async def requeue_terminal_job(
    conn: asyncpg.Connection,
    *,
    job_id: str,
    available_at: datetime,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE background_jobs
        SET status = 'retry_scheduled',
            available_at = $2,
            enqueued_at = NULL,
            started_at = NULL,
            finished_at = NULL,
            last_heartbeat_at = NULL,
            last_error_code = NULL,
            last_error = NULL,
            last_enqueue_error = NULL,
            lock_token = NULL,
            locked_by = NULL,
            updated_at = NOW()
        WHERE id = $1
          AND status IN ('failed', 'dead_letter')
        RETURNING *
        """,
        job_id,
        available_at,
    )


async def record_enqueue_success(conn: asyncpg.Connection, job_id: str) -> str:
    return await conn.execute(
        """
        UPDATE background_jobs
        SET enqueued_at = NOW(), last_enqueue_error = NULL, queue_publish_attempts = queue_publish_attempts + 1, updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
    )


async def record_enqueue_failure(conn: asyncpg.Connection, job_id: str, *, error_text: str) -> str:
    return await conn.execute(
        """
        UPDATE background_jobs
        SET last_enqueue_error = $2, queue_publish_attempts = queue_publish_attempts + 1, updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
        error_text,
    )


async def find_orphaned_queued_jobs(conn: asyncpg.Connection, *, limit: int = 100) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT *
        FROM background_jobs
        WHERE status = 'queued'
          AND enqueued_at IS NULL
        ORDER BY scheduled_for ASC
        LIMIT $1
        """,
        limit,
    )


async def find_due_retry_jobs(conn: asyncpg.Connection, *, limit: int = 100) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT *
        FROM background_jobs
        WHERE status = 'retry_scheduled'
          AND available_at <= NOW()
        ORDER BY available_at ASC
        LIMIT $1
        """,
        limit,
    )


async def find_stale_running_jobs(
    conn: asyncpg.Connection,
    *,
    stale_before: datetime,
    limit: int = 100,
) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT *
        FROM background_jobs
        WHERE status = 'running'
          AND last_heartbeat_at IS NOT NULL
          AND last_heartbeat_at < $1
        ORDER BY last_heartbeat_at ASC
        LIMIT $2
        """,
        stale_before,
        limit,
    )


async def rescue_stale_running_job(
    conn: asyncpg.Connection,
    *,
    job_id: str,
    available_at: datetime | None = None,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE background_jobs
        SET status = 'retry_scheduled',
            lock_token = NULL,
            locked_by = NULL,
            last_heartbeat_at = NULL,
            available_at = COALESCE($2, NOW()),
            updated_at = NOW()
        WHERE id = $1
          AND status = 'running'
        RETURNING *
        """,
        job_id,
        available_at,
    )


async def rescue_running_jobs_for_worker(
    conn: asyncpg.Connection,
    *,
    worker_id: str,
    available_at: datetime | None = None,
) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        UPDATE background_jobs
        SET status = 'retry_scheduled',
            lock_token = NULL,
            locked_by = NULL,
            last_heartbeat_at = NULL,
            available_at = COALESCE($2, NOW()),
            updated_at = NOW()
        WHERE status = 'running'
          AND locked_by = $1
        RETURNING *
        """,
        worker_id,
        available_at,
    )


async def touch_job_heartbeat(conn: asyncpg.Connection, job_id: str) -> str:
    return await conn.execute(
        """
        UPDATE background_jobs
        SET last_heartbeat_at = NOW(), updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
    )