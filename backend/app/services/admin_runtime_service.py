"""Read-only trust-layer observability queries for admin endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from app.core.config import settings
from app.jobs.arq import create_arq_pool, enqueue_job_message
from app.jobs.enums import RUNTIME_KIND_SCHEDULER, RUNTIME_KIND_WORKER
from app.repositories import command_repository, job_repository, runtime_heartbeat_repository
from app.services import admin_service


def _normalize_json(value: Any) -> dict[str, Any] | list[Any] | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, (dict, list)):
            return parsed
    return None


def _runtime_stale_after_seconds(runtime_kind: str) -> int:
    if runtime_kind == "worker":
        return max(settings.WORKER_HEARTBEAT_INTERVAL_SECONDS * 3, 30)
    if runtime_kind == "scheduler":
        return max(settings.SCHEDULER_POLL_INTERVAL_SECONDS * 3, 30)
    return 60


def _runtime_heartbeat_interval_seconds(runtime_kind: str) -> int:
    if runtime_kind == "worker":
        return settings.WORKER_HEARTBEAT_INTERVAL_SECONDS
    if runtime_kind == "scheduler":
        return settings.SCHEDULER_POLL_INTERVAL_SECONDS
    return 0


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _runtime_kinds(runtime_kind: str | None = None) -> list[str]:
    if runtime_kind is not None:
        return [runtime_kind]
    return [RUNTIME_KIND_WORKER, RUNTIME_KIND_SCHEDULER]


async def get_command_status(conn: asyncpg.Connection, command_id: str) -> dict[str, Any] | None:
    command_row = await conn.fetchrow("SELECT * FROM command_requests WHERE id = $1", command_id)
    if command_row is None:
        return None

    job_rows = await conn.fetch(
        """
        SELECT j.*, COALESCE(a.total_attempts, 0) AS total_attempts
        FROM background_jobs j
        LEFT JOIN (
            SELECT job_id, COUNT(*)::int AS total_attempts
            FROM background_job_attempts
            GROUP BY job_id
        ) a ON a.job_id = j.id
        WHERE j.command_id = $1
        ORDER BY j.created_at ASC
        """,
        command_id,
    )

    command = dict(command_row)
    command["id"] = str(command["id"])
    command["request_ip"] = str(command["request_ip"]) if command.get("request_ip") is not None else None
    command["payload_json"] = _normalize_json(command.get("payload_json"))
    command["result_json"] = _normalize_json(command.get("result_json"))
    command["jobs"] = []

    for row in job_rows:
        item = dict(row)
        total_attempts = max(int(item.get("attempt_count") or 0), int(item.get("total_attempts") or 0))
        command["jobs"].append(
            {
                "id": str(item["id"]),
                "kind": item["kind"],
                "queue_name": item["queue_name"],
                "status": item["status"],
                "attempt_count": total_attempts,
                "max_attempts": int(item["max_attempts"]),
                "queue_publish_attempts": int(item["queue_publish_attempts"]),
                "scheduled_for": item["scheduled_for"],
                "available_at": item["available_at"],
                "enqueued_at": item["enqueued_at"],
                "started_at": item["started_at"],
                "finished_at": item["finished_at"],
                "last_heartbeat_at": item["last_heartbeat_at"],
                "last_error_code": item["last_error_code"],
                "last_error": item["last_error"],
            }
        )

    return command


async def get_job_status(conn: asyncpg.Connection, job_id: str) -> dict[str, Any] | None:
    job_row = await conn.fetchrow("SELECT * FROM background_jobs WHERE id = $1", job_id)
    if job_row is None:
        return None

    attempts_rows = await conn.fetch(
        """
        SELECT *
        FROM background_job_attempts
        WHERE job_id = $1
        ORDER BY attempt_no ASC
        """,
        job_id,
    )

    command_row = None
    if job_row["command_id"] is not None:
        command_row = await conn.fetchrow(
            """
            SELECT id, command_kind, status, request_id, trace_id,
                   requested_by_admin_id, requested_by_user_id,
                   submitted_at, started_at, finished_at
            FROM command_requests
            WHERE id = $1
            """,
            str(job_row["command_id"]),
        )

    job = dict(job_row)
    job["id"] = str(job["id"])
    job["command_id"] = str(job["command_id"]) if job.get("command_id") is not None else None
    job["lock_token"] = str(job["lock_token"]) if job.get("lock_token") is not None else None
    job["entity_id"] = str(job["entity_id"]) if job.get("entity_id") is not None else None
    job["priority"] = int(job["priority"])
    job["queue_publish_attempts"] = int(job["queue_publish_attempts"])
    job["attempt_count"] = max(int(job["attempt_count"]), len(attempts_rows))
    job["max_attempts"] = int(job["max_attempts"])
    job["payload_json"] = _normalize_json(job.get("payload_json"))
    job["attempts"] = []

    if command_row is not None:
        command = dict(command_row)
        command["id"] = str(command["id"])
        job["command"] = command
    else:
        job["command"] = None

    for row in attempts_rows:
        attempt = dict(row)
        attempt["id"] = str(attempt["id"])
        attempt["job_id"] = str(attempt["job_id"])
        attempt["attempt_no"] = int(attempt["attempt_no"])
        attempt["duration_ms"] = int(attempt["duration_ms"]) if attempt.get("duration_ms") is not None else None
        job["attempts"].append(attempt)

    return job


async def list_operations(
    conn: asyncpg.Connection,
    *,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    action: str | None = None,
    actor_admin_id: str | None = None,
    submitted_from: datetime | None = None,
    submitted_to: datetime | None = None,
) -> dict[str, Any]:
    conditions = ["c.requested_by_admin_id IS NOT NULL"]
    args: list[Any] = []
    idx = 1

    if status:
        conditions.append(f"(c.status = ${idx} OR j.status = ${idx})")
        args.append(status)
        idx += 1
    if action:
        conditions.append(f"c.command_kind = ${idx}")
        args.append(action)
        idx += 1
    if actor_admin_id:
        conditions.append(f"c.requested_by_admin_id = ${idx}")
        args.append(actor_admin_id)
        idx += 1
    if submitted_from:
        conditions.append(f"c.submitted_at >= ${idx}")
        args.append(submitted_from)
        idx += 1
    if submitted_to:
        conditions.append(f"c.submitted_at <= ${idx}")
        args.append(submitted_to)
        idx += 1

    where_clause = " AND ".join(conditions)
    base = f"""
        FROM command_requests c
        LEFT JOIN LATERAL (
            SELECT *
            FROM background_jobs bj
            WHERE bj.command_id = c.id
            ORDER BY bj.created_at DESC
            LIMIT 1
        ) j ON TRUE
        WHERE {where_clause}
    """

    total = await conn.fetchval(f"SELECT COUNT(*) {base}", *args)
    rows = await conn.fetch(
        f"""
        SELECT
            c.id AS command_id,
            c.command_kind AS action,
            c.status AS command_status,
            c.requested_by_admin_id AS actor_admin_id,
            c.requested_by_user_id AS actor_user_id,
            c.request_id,
            c.trace_id,
            c.submitted_at,
            c.started_at,
            c.finished_at,
            j.id AS job_id,
            j.kind AS job_kind,
            j.status AS job_status,
            j.queue_name
        {base}
        ORDER BY c.submitted_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *args,
        page_size,
        (page - 1) * page_size,
    )

    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["command_id"] = str(item["command_id"])
        item["job_id"] = str(item["job_id"]) if item.get("job_id") is not None else None
        items.append(item)

    total_count = int(total or 0)
    return {
        "items": items,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total_count,
    }


async def list_runtime_heartbeats(
    conn: asyncpg.Connection,
    *,
    runtime_kind: str | None = None,
    limit: int = 100,
    active_only: bool = True,
) -> dict[str, Any]:
    args: list[Any] = []
    query = """
        SELECT id, runtime_kind, runtime_id, hostname, pid, started_at, last_seen_at, meta_json
        FROM runtime_heartbeats
    """
    if runtime_kind:
        query += " WHERE runtime_kind = $1"
        args.append(runtime_kind)
    query += " ORDER BY runtime_kind ASC, last_seen_at DESC"
    rows = await conn.fetch(query, *args)

    now = datetime.now(timezone.utc)
    runtime_entries: list[dict[str, Any]] = []
    stale_total = 0
    active_workers = 0
    active_schedulers = 0
    stale_workers = 0
    stale_schedulers = 0
    leader_runtime_id: str | None = None
    leader_count = 0
    for row in rows:
        item = dict(row)
        item["id"] = str(item["id"])
        item["pid"] = int(item["pid"])
        item["meta_json"] = _normalize_json(item.get("meta_json"))
        stale_after_seconds = _runtime_stale_after_seconds(item["runtime_kind"])
        heartbeat_interval_seconds = _runtime_heartbeat_interval_seconds(item["runtime_kind"])
        seconds_since_last_seen = max(int((now - item["last_seen_at"]).total_seconds()), 0)
        started_age_seconds = max(int((now - item["started_at"]).total_seconds()), 0)
        is_stale = seconds_since_last_seen > stale_after_seconds
        meta_json = item["meta_json"] if isinstance(item["meta_json"], dict) else {}
        is_leader = meta_json.get("is_leader") if isinstance(meta_json.get("is_leader"), bool) else None
        lease_ttl_seconds = _coerce_int(meta_json.get("lease_ttl_seconds"))
        queue_name = meta_json.get("queue") or meta_json.get("queue_name")
        lease_expires_in_seconds = None
        if lease_ttl_seconds is not None:
            lease_expires_in_seconds = max(lease_ttl_seconds - seconds_since_last_seen, 0)

        stale_total += int(is_stale)
        if item["runtime_kind"] == RUNTIME_KIND_WORKER:
            if is_stale:
                stale_workers += 1
            else:
                active_workers += 1
        elif item["runtime_kind"] == RUNTIME_KIND_SCHEDULER:
            if is_stale:
                stale_schedulers += 1
            else:
                active_schedulers += 1
                if is_leader:
                    leader_count += 1
                    if leader_runtime_id is None:
                        leader_runtime_id = item["runtime_id"]

        item["queue_name"] = str(queue_name) if queue_name is not None else None
        item["heartbeat_interval_seconds"] = heartbeat_interval_seconds
        item["stale_after_seconds"] = stale_after_seconds
        item["started_age_seconds"] = started_age_seconds
        item["seconds_since_last_seen"] = seconds_since_last_seen
        item["is_stale"] = is_stale
        item["is_leader"] = is_leader
        item["lease_ttl_seconds"] = lease_ttl_seconds
        item["lease_expires_in_seconds"] = lease_expires_in_seconds
        runtime_entries.append(item)

    if active_only:
        runtime_entries = [item for item in runtime_entries if not item["is_stale"]]

    runtime_entries = runtime_entries[:limit]

    return {
        "generated_at": now,
        "active_only": active_only,
        "total": len(runtime_entries),
        "stale_total": stale_total,
        "active_workers": active_workers,
        "active_schedulers": active_schedulers,
        "stale_workers": stale_workers,
        "stale_schedulers": stale_schedulers,
        "leader_runtime_id": leader_runtime_id,
        "leader_count": leader_count,
        "runtimes": runtime_entries,
    }


async def prune_runtime_heartbeats(
    conn: asyncpg.Connection,
    *,
    runtime_kind: str | None = None,
    stale_only: bool = True,
    retention_seconds: int | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    effective_retention_seconds = retention_seconds if retention_seconds is not None else settings.RUNTIME_HEARTBEAT_RETENTION_SECONDS

    deleted_count = 0
    for kind in _runtime_kinds(runtime_kind):
        cutoff_seconds = effective_retention_seconds
        if stale_only:
            cutoff_seconds += _runtime_stale_after_seconds(kind)
        prune_before = now - timedelta(seconds=cutoff_seconds)
        deleted_count += await runtime_heartbeat_repository.delete_stale_runtimes(
            conn,
            runtime_kind=kind,
            stale_before=prune_before,
        )

    return {
        "pruned_at": now,
        "runtime_kind": runtime_kind,
        "stale_only": stale_only,
        "retention_seconds": effective_retention_seconds,
        "deleted_count": deleted_count,
    }


async def requeue_job(
    conn: asyncpg.Connection,
    *,
    job_id: str,
    admin_id: str,
    reason: str | None = None,
    request_ip: str | None = None,
) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)

    async with conn.transaction():
        job = await conn.fetchrow(
            "SELECT * FROM background_jobs WHERE id = $1 FOR UPDATE",
            job_id,
        )
        if job is None:
            return None

        previous_status = str(job["status"])
        if previous_status not in {"failed", "dead_letter"}:
            raise ValueError("Only failed or dead-letter jobs can be requeued manually")

        replayed = await job_repository.requeue_terminal_job(
            conn,
            job_id=job_id,
            available_at=now,
        )
        if replayed is None:
            raise ValueError("Job could not be requeued")

        if replayed.get("command_id") is not None:
            await command_repository.reset_command_for_replay(
                conn,
                str(replayed["command_id"]),
            )

        await admin_service.log_admin_action(
            conn,
            admin_id=admin_id,
            action="runtime_requeue_job",
            target_type="background_job",
            target_id=str(replayed["id"]),
            old_value={
                "status": previous_status,
                "attempt_count": int(job.get("attempt_count") or 0),
                "queue_name": job.get("queue_name"),
                "last_error_code": job.get("last_error_code"),
            },
            new_value={
                "status": "retry_scheduled",
                "queue_name": replayed.get("queue_name"),
                "reason": reason,
            },
            ip_address=request_ip,
            command_id=str(replayed["command_id"]) if replayed.get("command_id") is not None else None,
            job_id=str(replayed["id"]),
            request_id=replayed.get("request_id"),
            trace_id=replayed.get("trace_id"),
        )

    enqueue_error: str | None = None
    enqueued = False
    redis = None
    try:
        redis = await create_arq_pool()
        await enqueue_job_message(
            redis,
            job_id=job_id,
            queue_name=str(replayed["queue_name"]),
            trace_id=replayed.get("trace_id"),
            request_id=replayed.get("request_id"),
        )
        async with conn.transaction():
            await job_repository.record_enqueue_success(conn, job_id)
        enqueued = True
    except Exception as exc:
        enqueue_error = str(exc)
        async with conn.transaction():
            await job_repository.record_enqueue_failure(conn, job_id, error_text=enqueue_error)
    finally:
        if redis is not None:
            await redis.close(close_connection_pool=True)

    return {
        "job_id": str(replayed["id"]),
        "previous_status": previous_status,
        "status": "retry_scheduled",
        "queue_name": str(replayed["queue_name"]),
        "enqueued": enqueued,
        "enqueue_error": enqueue_error,
        "message": "Job requeued and published to the worker queue" if enqueued else "Job requeued; scheduler will retry enqueue automatically",
    }