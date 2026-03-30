"""Worker process skeleton for trust-layer jobs."""

from __future__ import annotations

import json
import logging
import socket
from datetime import timedelta
from uuid import uuid4

from app.db.session import acquire_db_connection, close_db_pool, ensure_db_pool
from app.jobs.arq import build_worker_settings, validate_job_message
from app.jobs.context import JobContext
from app.jobs.enums import QUEUE_OPS, RUNTIME_KIND_WORKER
from app.jobs.registry import get_handler
from app.repositories import command_repository, job_repository, runtime_heartbeat_repository


logger = logging.getLogger(__name__)


def build_worker_id(*, hostname: str | None = None, pid: int | None = None) -> str:
    import os

    return f"{hostname or socket.gethostname()}:{pid or os.getpid()}"


def make_lock_token() -> str:
    return str(uuid4())


def _coerce_payload_json(payload_json) -> dict:
    if payload_json is None:
        return {}
    if isinstance(payload_json, str):
        payload_json = json.loads(payload_json)
    if not isinstance(payload_json, dict):
        raise ValueError("job payload_json must decode to an object")
    return payload_json


async def refresh_runtime_heartbeat(conn, *, worker_id: str, now) -> None:
    hostname, pid_str = worker_id.split(":", 1)
    await runtime_heartbeat_repository.upsert_runtime_heartbeat(
        conn,
        runtime_kind=RUNTIME_KIND_WORKER,
        runtime_id=worker_id,
        hostname=hostname,
        pid=int(pid_str),
        started_at=now,
        last_seen_at=now,
        meta_json={"queue": QUEUE_OPS},
    )


async def execute_job_payload(conn, payload: dict, *, worker_id: str | None = None) -> dict:
    message = validate_job_message(payload)
    effective_worker_id = worker_id or build_worker_id()
    claimed_lock_token = make_lock_token()

    job = await job_repository.get_job_by_id(conn, message["job_id"])
    if job is None:
        raise ValueError(f"Job not found: {message['job_id']}")

    handler = get_handler(job["kind"])
    claimed = await job_repository.claim_job(
        conn,
        job_id=message["job_id"],
        worker_id=effective_worker_id,
        lock_token=claimed_lock_token,
    )
    if claimed is None:
        return {"status": "ignored", "reason": "not-claimable", "job_id": message["job_id"]}

    if claimed.get("command_id"):
        await command_repository.mark_command_running(conn, claimed["command_id"])

    now = JobContext(worker_id=effective_worker_id).now_factory()
    await runtime_heartbeat_repository.upsert_runtime_heartbeat(
        conn,
        runtime_kind=RUNTIME_KIND_WORKER,
        runtime_id=effective_worker_id,
        hostname=effective_worker_id.split(":", 1)[0],
        pid=int(effective_worker_id.split(":", 1)[1]),
        started_at=now,
        last_seen_at=now,
        meta_json={"queue": claimed.get("queue_name", QUEUE_OPS)},
    )

    attempt_no = int(claimed.get("attempt_count", 0)) + 1
    await job_repository.insert_attempt(
        conn,
        job_id=claimed["id"],
        attempt_no=attempt_no,
        worker_id=effective_worker_id,
        started_at=now,
    )

    context = JobContext(
        job_id=claimed["id"],
        worker_id=effective_worker_id,
        trace_id=message.get("trace_id"),
        request_id=message.get("request_id"),
        heartbeat=lambda: job_repository.touch_job_heartbeat(conn, claimed["id"]),
    )

    try:
        result = await handler.execute(conn, _coerce_payload_json(claimed.get("payload_json")), context)
        await job_repository.mark_job_succeeded(conn, claimed["id"])
        if claimed.get("command_id"):
            await command_repository.mark_command_succeeded(conn, claimed["command_id"], result_json=result)
        return {"status": "succeeded", "job_id": claimed["id"], "result": result}
    except Exception as exc:
        if handler.is_retryable(exc):
            max_attempts = int(claimed.get("max_attempts") or handler.max_attempts)
            if attempt_no >= max_attempts:
                await job_repository.mark_job_dead_letter(
                    conn,
                    claimed["id"],
                    error_code=exc.__class__.__name__,
                    error_text=str(exc),
                )
            else:
                backoff = handler.backoff_seconds(attempt_no, exc.__class__.__name__)
                await job_repository.mark_job_retry_scheduled(
                    conn,
                    claimed["id"],
                    error_code=exc.__class__.__name__,
                    error_text=str(exc),
                    available_at=context.now_factory() + timedelta(seconds=backoff),
                )
            if claimed.get("command_id"):
                await command_repository.mark_command_failed(
                    conn,
                    claimed["command_id"],
                    error_code=exc.__class__.__name__,
                    error_text=str(exc),
                )
            return {"status": "retryable-failure", "job_id": claimed["id"]}

        await job_repository.mark_job_failed(
            conn,
            claimed["id"],
            error_code=exc.__class__.__name__,
            error_text=str(exc),
        )
        if claimed.get("command_id"):
            await command_repository.mark_command_failed(
                conn,
                claimed["command_id"],
                error_code=exc.__class__.__name__,
                error_text=str(exc),
            )
        return {"status": "failed", "job_id": claimed["id"]}


async def process_job_message(ctx: dict, payload: dict) -> dict:
    worker_id = ctx.get("worker_id") or build_worker_id()
    async with acquire_db_connection() as conn:
        return await execute_job_payload(conn, payload, worker_id=worker_id)


async def worker_startup(ctx: dict) -> None:
    await ensure_db_pool()
    ctx["worker_id"] = build_worker_id()


async def worker_shutdown(ctx: dict) -> None:
    worker_id = ctx.get("worker_id")
    if worker_id:
        async with acquire_db_connection() as conn:
            rescued_jobs = await job_repository.rescue_running_jobs_for_worker(
                conn,
                worker_id=worker_id,
            )
        if rescued_jobs:
            logger.info(
                "Worker %s released %s running jobs during shutdown",
                worker_id,
                len(rescued_jobs),
            )
    await close_db_pool()


WorkerSettings = build_worker_settings(
    functions=[process_job_message],
    queue_name=QUEUE_OPS,
    on_startup=worker_startup,
    on_shutdown=worker_shutdown,
)