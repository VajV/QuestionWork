"""Scheduler process skeleton for trust-layer jobs."""

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import settings
from app.db.session import acquire_db_connection, close_db_pool, ensure_db_pool
from app.jobs.arq import create_arq_pool, enqueue_job_message
from app.jobs.enums import RUNTIME_KIND_SCHEDULER, RUNTIME_KIND_WORKER
from app.repositories import job_repository, runtime_heartbeat_repository
from app.services import analytics_service
from app.services import lifecycle_runtime_service, lifecycle_service
from app.services import withdrawal_runtime_service
from app.services import dispute_service
from app.services import email_runtime_service
from app.services import event_service
from app.services import saved_searches_service
from app.services import class_service
from app.services import challenge_service

logger = logging.getLogger(__name__)

SCHEDULER_LEASE_KEY = "questionwork:runtime:scheduler:leader"
LIFECYCLE_SCAN_INTERVAL_KEY = "questionwork:runtime:lifecycle:scan"
SAVED_SEARCH_ALERT_KEY = "questionwork:runtime:saved_search_alerts:last_run"
ABILITY_EXPIRY_KEY = "questionwork:runtime:ability_expiry:last_run"
_SCHEDULER_LEASE_RENEW_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return 0
"""
_SCHEDULER_LEASE_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


def build_scheduler_id(*, hostname: str | None = None, pid: int | None = None) -> str:
    import os

    return f"{hostname or socket.gethostname()}:{pid or os.getpid()}"


def _runtime_stale_after_seconds(runtime_kind: str) -> int:
    if runtime_kind == RUNTIME_KIND_WORKER:
        return max(settings.WORKER_HEARTBEAT_INTERVAL_SECONDS * 3, 30)
    if runtime_kind == RUNTIME_KIND_SCHEDULER:
        return max(settings.SCHEDULER_POLL_INTERVAL_SECONDS * 3, 30)
    return 60


def _scheduler_lease_ttl_seconds() -> int:
    return max(settings.SCHEDULER_POLL_INTERVAL_SECONDS * 3, 30)


def _scheduler_failure_backoff_seconds(consecutive_failures: int) -> int:
    base_delay = max(settings.SCHEDULER_POLL_INTERVAL_SECONDS, 5)
    return min(base_delay * max(consecutive_failures, 1), 60)


def _stale_running_recovery_seconds() -> int:
    heartbeat_bound = max(settings.WORKER_HEARTBEAT_INTERVAL_SECONDS * 3, 45)
    return min(settings.STALE_RUNNING_TIMEOUT_SECONDS, heartbeat_bound)


def build_scheduler_lease_value(*, scheduler_id: str, lease_token: str) -> str:
    return f"{scheduler_id}|{lease_token}"


async def acquire_or_renew_scheduler_lease(
    redis,
    *,
    scheduler_id: str,
    lease_token: str,
    ttl_seconds: int | None = None,
) -> bool:
    owner_value = build_scheduler_lease_value(scheduler_id=scheduler_id, lease_token=lease_token)
    lease_ttl = ttl_seconds or _scheduler_lease_ttl_seconds()
    acquired = await redis.set(SCHEDULER_LEASE_KEY, owner_value, ex=lease_ttl, nx=True)
    if acquired:
        return True
    renewed = await redis.eval(
        _SCHEDULER_LEASE_RENEW_SCRIPT,
        1,
        SCHEDULER_LEASE_KEY,
        owner_value,
        str(lease_ttl),
    )
    return bool(renewed)


async def release_scheduler_lease(
    redis,
    *,
    scheduler_id: str,
    lease_token: str,
) -> bool:
    owner_value = build_scheduler_lease_value(scheduler_id=scheduler_id, lease_token=lease_token)
    released = await redis.eval(
        _SCHEDULER_LEASE_RELEASE_SCRIPT,
        1,
        SCHEDULER_LEASE_KEY,
        owner_value,
    )
    return bool(released)


async def refresh_scheduler_runtime_heartbeat(
    conn,
    *,
    scheduler_id: str,
    now: datetime,
    is_leader: bool,
) -> None:
    hostname, pid_str = scheduler_id.split(":", 1)
    await runtime_heartbeat_repository.upsert_runtime_heartbeat(
        conn,
        runtime_kind=RUNTIME_KIND_SCHEDULER,
        runtime_id=scheduler_id,
        hostname=hostname,
        pid=int(pid_str),
        started_at=now,
        last_seen_at=now,
        meta_json={
            "is_leader": is_leader,
            "poll_interval_seconds": settings.SCHEDULER_POLL_INTERVAL_SECONDS,
            "lease_ttl_seconds": _scheduler_lease_ttl_seconds(),
            "orphaned_recovery_interval_seconds": settings.ORPHANED_QUEUED_RECOVERY_INTERVAL_SECONDS,
            "stale_running_recovery_seconds": _stale_running_recovery_seconds(),
        },
    )


async def acquire_periodic_scheduler_slot(redis, *, slot_key: str, ttl_seconds: int) -> bool:
    return bool(await redis.set(slot_key, "1", ex=max(ttl_seconds, 1), nx=True))


async def run_lifecycle_scan(conn) -> None:
    dormant_count = await lifecycle_service.scan_and_enqueue_dormant_clients(conn)
    stale_count = await lifecycle_service.scan_and_enqueue_stale_shortlists(conn)
    logger.info(
        "Lifecycle scan complete: dormant_clients_enqueued=%s stale_shortlists_enqueued=%s",
        dormant_count,
        stale_count,
    )


async def scheduler_tick(
    conn,
    *,
    enqueue_callable,
    scheduler_id: str,
    now: datetime | None = None,
) -> dict[str, int]:
    tick_now = now or datetime.now(timezone.utc)
    await refresh_scheduler_runtime_heartbeat(
        conn,
        scheduler_id=scheduler_id,
        now=tick_now,
        is_leader=True,
    )
    for runtime_kind in (RUNTIME_KIND_WORKER, RUNTIME_KIND_SCHEDULER):
        prune_before = tick_now - timedelta(
            seconds=_runtime_stale_after_seconds(runtime_kind) + settings.RUNTIME_HEARTBEAT_RETENTION_SECONDS
        )
        await runtime_heartbeat_repository.delete_stale_runtimes(
            conn,
            runtime_kind=runtime_kind,
            stale_before=prune_before,
        )

    if settings.WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED:
        await withdrawal_runtime_service.schedule_auto_approve_jobs(
            conn,
            auto_approve_limit=settings.WITHDRAWAL_AUTO_APPROVE_LIMIT,
            batch_limit=settings.WITHDRAWAL_AUTO_APPROVE_BATCH_LIMIT,
        )

    # Schedule email outbox delivery via ARQ worker
    if settings.EMAILS_ENABLED:
        await email_runtime_service.schedule_email_outbox_jobs(conn)

    if settings.EMAILS_ENABLED and settings.LIFECYCLE_DELIVERY_JOBS_ENABLED:
        try:
            await lifecycle_runtime_service.schedule_due_lifecycle_jobs(
                conn,
                batch_limit=settings.LIFECYCLE_DELIVERY_BATCH_LIMIT,
            )
        except Exception:
            logger.exception("Lifecycle delivery job scheduling failed during scheduler tick")

    if hasattr(conn, "fetchval"):
        try:
            await analytics_service.prune_old_events(
                conn,
                retention_days=settings.ANALYTICS_EVENTS_RETENTION_DAYS,
            )
        except Exception:
            logger.exception("Analytics retention prune failed during scheduler tick")

    # Auto-escalate disputes whose response deadline has passed.
    # Guard with hasattr so minimal test mocks (conn=object()) are skipped safely.
    if hasattr(conn, "fetchval"):
        overdue_dispute_count = await conn.fetchval(
            "SELECT COUNT(*) FROM disputes WHERE auto_escalate_at <= $1 AND status = ANY(ARRAY['open','responded']::text[])",
            tick_now,
        )
        if overdue_dispute_count:
            try:
                async with conn.transaction():
                    await dispute_service.auto_escalate_overdue(conn)
            except Exception:
                logger.exception("Dispute auto-escalation failed during scheduler tick")

    # Auto-activate / auto-end events
    if hasattr(conn, "fetchval"):
        try:
            async with conn.transaction():
                await event_service.auto_activate_due_events(conn)
                await event_service.auto_end_due_events(conn)
        except Exception:
            logger.exception("Event lifecycle (activate/end) failed during scheduler tick")

    # Saved search alert notifications
    if settings.SAVED_SEARCH_ALERTS_ENABLED and hasattr(conn, "fetchval"):
        try:
            alerted = await saved_searches_service.run_alert_scan(
                conn, batch_limit=settings.SAVED_SEARCH_ALERT_BATCH_LIMIT
            )
            if alerted:
                logger.info("Saved search alerts: %d notification(s) sent", alerted)
        except Exception:
            logger.exception("Saved search alert scan failed during scheduler tick")

    # RPG ability expiry (clears stale active_until rows, applies post-rage burnout)
    if hasattr(conn, "fetchval"):
        try:
            await class_service.expire_stale_abilities(conn)
        except Exception:
            logger.exception("Ability expiry scan failed during scheduler tick")

    # Weekly challenges seed (idempotent — creates challenges for current week if missing)
    if settings.WEEKLY_CHALLENGES_ENABLED and hasattr(conn, "fetchval"):
        try:
            async with conn.transaction():
                await challenge_service.ensure_weekly_challenges(conn)
        except Exception:
            logger.exception("Weekly challenges seed failed during scheduler tick")

    orphaned_count = retry_count = rescued_count = 0

    orphaned_jobs = await job_repository.find_orphaned_queued_jobs(conn)
    for job in orphaned_jobs:
        try:
            await enqueue_callable(job_id=job["id"], queue_name=job.get("queue_name"), trace_id=job.get("trace_id"), request_id=job.get("request_id"))
        except Exception as exc:
            await job_repository.record_enqueue_failure(conn, job["id"], error_text=str(exc))
            continue
        await job_repository.record_enqueue_success(conn, job["id"])
        orphaned_count += 1

    retry_jobs = await job_repository.find_due_retry_jobs(conn)
    for job in retry_jobs:
        try:
            await enqueue_callable(job_id=job["id"], queue_name=job.get("queue_name"), trace_id=job.get("trace_id"), request_id=job.get("request_id"))
        except Exception as exc:
            await job_repository.record_enqueue_failure(conn, job["id"], error_text=str(exc))
            continue
        await job_repository.record_enqueue_success(conn, job["id"])
        retry_count += 1

    stale_before = tick_now - timedelta(seconds=_stale_running_recovery_seconds())
    stale_jobs = await job_repository.find_stale_running_jobs(conn, stale_before=stale_before)
    for job in stale_jobs:
        rescued = await job_repository.rescue_stale_running_job(conn, job_id=job["id"], available_at=tick_now)
        if rescued is None:
            continue
        try:
            await enqueue_callable(job_id=rescued["id"], queue_name=rescued.get("queue_name"), trace_id=rescued.get("trace_id"), request_id=rescued.get("request_id"))
        except Exception as exc:
            await job_repository.record_enqueue_failure(conn, rescued["id"], error_text=str(exc))
            continue
        await job_repository.record_enqueue_success(conn, rescued["id"])
        rescued_count += 1

    return {
        "orphaned_enqueued": orphaned_count,
        "retry_enqueued": retry_count,
        "rescued_running": rescued_count,
    }


async def run_scheduler_iteration(
    conn,
    *,
    redis,
    enqueue_callable,
    scheduler_id: str,
    lease_token: str,
    now: datetime | None = None,
    tick_callable=scheduler_tick,
) -> dict[str, int] | None:
    iteration_now = now or datetime.now(timezone.utc)
    has_lease = await acquire_or_renew_scheduler_lease(
        redis,
        scheduler_id=scheduler_id,
        lease_token=lease_token,
    )
    if not has_lease:
        await refresh_scheduler_runtime_heartbeat(
            conn,
            scheduler_id=scheduler_id,
            now=iteration_now,
            is_leader=False,
        )
        return None

    result = await tick_callable(
        conn,
        enqueue_callable=enqueue_callable,
        scheduler_id=scheduler_id,
        now=iteration_now,
    )

    if settings.LIFECYCLE_SCAN_ENABLED:
        try:
            should_run_scan = await acquire_periodic_scheduler_slot(
                redis,
                slot_key=LIFECYCLE_SCAN_INTERVAL_KEY,
                ttl_seconds=settings.LIFECYCLE_SCAN_INTERVAL_SECONDS,
            )
            if should_run_scan:
                await run_lifecycle_scan(conn)
        except Exception:
            logger.exception("Lifecycle scan failed during scheduler iteration")

    return result


async def run_scheduler_loop() -> None:
    await ensure_db_pool()
    scheduler_id = build_scheduler_id()
    lease_token = uuid4().hex
    redis = await create_arq_pool()
    consecutive_failures = 0
    try:
        while True:
            try:
                async with acquire_db_connection() as conn:
                    await run_scheduler_iteration(
                        conn,
                        redis=redis,
                        enqueue_callable=lambda **kwargs: enqueue_job_message(redis, function_name="process_job_message", **kwargs),
                        scheduler_id=scheduler_id,
                        lease_token=lease_token,
                    )
                consecutive_failures = 0
                await asyncio.sleep(settings.SCHEDULER_POLL_INTERVAL_SECONDS)
            except Exception:
                consecutive_failures += 1
                delay_seconds = _scheduler_failure_backoff_seconds(consecutive_failures)
                logger.exception(
                    "Scheduler iteration failed; backing off for %s seconds",
                    delay_seconds,
                )
                await asyncio.sleep(delay_seconds)
    finally:
        try:
            await release_scheduler_lease(
                redis,
                scheduler_id=scheduler_id,
                lease_token=lease_token,
            )
        except Exception:
            logger.debug("Failed to release scheduler lease cleanly", exc_info=True)
        await redis.close(close_connection_pool=True)
        await close_db_pool()


def main() -> None:
    asyncio.run(run_scheduler_loop())


if __name__ == "__main__":
    main()