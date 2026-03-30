from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.jobs import scheduler as scheduler_runtime


class FakeRedisLease:
    def __init__(self):
        self._now = 0
        self._values: dict[str, tuple[str, int]] = {}

    def advance(self, seconds: int) -> None:
        self._now += seconds

    def _prune(self) -> None:
        expired_keys = [key for key, (_, expires_at) in self._values.items() if expires_at <= self._now]
        for key in expired_keys:
            self._values.pop(key, None)

    async def set(self, key: str, value: str, *, ex: int, nx: bool = False):
        self._prune()
        if nx and key in self._values:
            return False
        self._values[key] = (value, self._now + ex)
        return True

    async def eval(self, script: str, _num_keys: int, key: str, expected_value: str, *args):
        self._prune()
        current = self._values.get(key)
        if current is None or current[0] != expected_value:
            return 0
        if script == scheduler_runtime._SCHEDULER_LEASE_RENEW_SCRIPT:
            ttl_seconds = int(args[0])
            self._values[key] = (expected_value, self._now + ttl_seconds)
            return 1
        if script == scheduler_runtime._SCHEDULER_LEASE_RELEASE_SCRIPT:
            self._values.pop(key, None)
            return 1
        raise AssertionError(f"Unexpected Lua script: {script}")


@pytest.mark.asyncio
async def test_scheduler_finds_orphaned_queued_jobs_with_missing_enqueued_at_and_reenqueues_them(monkeypatch):
    conn = object()
    job = {"id": "job-1", "queue_name": "ops", "trace_id": "t-1", "request_id": "r-1"}
    enqueue = AsyncMock()

    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "delete_stale_runtimes", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.withdrawal_runtime_service, "schedule_auto_approve_jobs", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_orphaned_queued_jobs", AsyncMock(return_value=[job]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_due_retry_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_stale_running_jobs", AsyncMock(return_value=[]))
    record_enqueue_success = AsyncMock()
    monkeypatch.setattr(scheduler_runtime.job_repository, "record_enqueue_success", record_enqueue_success)

    result = await scheduler_runtime.scheduler_tick(conn, enqueue_callable=enqueue, scheduler_id="host:100", now=datetime.now(timezone.utc))

    assert result["orphaned_enqueued"] == 1
    enqueue.assert_awaited_once()
    record_enqueue_success.assert_awaited_once_with(conn, "job-1")


@pytest.mark.asyncio
async def test_scheduler_finds_due_retry_jobs_and_reenqueues_them(monkeypatch):
    conn = object()
    job = {"id": "job-2", "queue_name": "ops", "trace_id": None, "request_id": None}
    enqueue = AsyncMock()

    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "delete_stale_runtimes", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.withdrawal_runtime_service, "schedule_auto_approve_jobs", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_orphaned_queued_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_due_retry_jobs", AsyncMock(return_value=[job]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_stale_running_jobs", AsyncMock(return_value=[]))
    record_enqueue_success = AsyncMock()
    monkeypatch.setattr(scheduler_runtime.job_repository, "record_enqueue_success", record_enqueue_success)

    result = await scheduler_runtime.scheduler_tick(conn, enqueue_callable=enqueue, scheduler_id="host:100", now=datetime.now(timezone.utc))

    assert result["retry_enqueued"] == 1
    enqueue.assert_awaited_once()
    record_enqueue_success.assert_awaited_once_with(conn, "job-2")


@pytest.mark.asyncio
async def test_scheduler_rescues_stale_running_jobs_reuses_same_job_id_and_never_creates_duplicate_rows(monkeypatch):
    conn = object()
    stale_job = {"id": "job-3", "queue_name": "ops", "trace_id": "t-3", "request_id": "r-3"}
    rescued_job = {"id": "job-3", "queue_name": "ops", "trace_id": "t-3", "request_id": "r-3"}
    enqueue = AsyncMock()

    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "delete_stale_runtimes", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.withdrawal_runtime_service, "schedule_auto_approve_jobs", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_orphaned_queued_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_due_retry_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_stale_running_jobs", AsyncMock(return_value=[stale_job]))
    rescue = AsyncMock(return_value=rescued_job)
    monkeypatch.setattr(scheduler_runtime.job_repository, "rescue_stale_running_job", rescue)
    record_enqueue_success = AsyncMock()
    monkeypatch.setattr(scheduler_runtime.job_repository, "record_enqueue_success", record_enqueue_success)

    result = await scheduler_runtime.scheduler_tick(conn, enqueue_callable=enqueue, scheduler_id="host:100", now=datetime.now(timezone.utc))

    assert result["rescued_running"] == 1
    rescue.assert_awaited_once()
    enqueue.assert_awaited_once()
    assert enqueue.await_args.kwargs["job_id"] == "job-3"
    record_enqueue_success.assert_awaited_once_with(conn, "job-3")


@pytest.mark.asyncio
async def test_scheduler_writes_its_runtime_heartbeat(monkeypatch):
    conn = object()
    enqueue = AsyncMock()
    heartbeat = AsyncMock()
    now = datetime.now(timezone.utc)

    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", heartbeat)
    prune = AsyncMock(return_value=3)
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "delete_stale_runtimes", prune)
    monkeypatch.setattr(scheduler_runtime.withdrawal_runtime_service, "schedule_auto_approve_jobs", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_orphaned_queued_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_due_retry_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_stale_running_jobs", AsyncMock(return_value=[]))

    result = await scheduler_runtime.scheduler_tick(conn, enqueue_callable=enqueue, scheduler_id="host:100", now=now)

    assert result == {"orphaned_enqueued": 0, "retry_enqueued": 0, "rescued_running": 0}
    heartbeat.assert_awaited_once()
    assert prune.await_count == 2


@pytest.mark.asyncio
async def test_scheduler_records_enqueue_failure_without_counting_job_as_enqueued(monkeypatch):
    conn = object()
    job = {"id": "job-4", "queue_name": "ops", "trace_id": None, "request_id": None}
    enqueue = AsyncMock(side_effect=RuntimeError("redis publish failed"))
    record_enqueue_failure = AsyncMock()
    record_enqueue_success = AsyncMock()

    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "delete_stale_runtimes", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.withdrawal_runtime_service, "schedule_auto_approve_jobs", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_orphaned_queued_jobs", AsyncMock(return_value=[job]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_due_retry_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_stale_running_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "record_enqueue_failure", record_enqueue_failure)
    monkeypatch.setattr(scheduler_runtime.job_repository, "record_enqueue_success", record_enqueue_success)

    result = await scheduler_runtime.scheduler_tick(conn, enqueue_callable=enqueue, scheduler_id="host:100", now=datetime.now(timezone.utc))

    assert result == {"orphaned_enqueued": 0, "retry_enqueued": 0, "rescued_running": 0}
    record_enqueue_failure.assert_awaited_once_with(conn, "job-4", error_text="redis publish failed")
    record_enqueue_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduler_prunes_stale_runtime_heartbeats_using_retention_cutoff(monkeypatch):
    conn = object()
    enqueue = AsyncMock()
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    prune = AsyncMock(return_value=2)
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "delete_stale_runtimes", prune)
    monkeypatch.setattr(scheduler_runtime.withdrawal_runtime_service, "schedule_auto_approve_jobs", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_orphaned_queued_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_due_retry_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_stale_running_jobs", AsyncMock(return_value=[]))

    await scheduler_runtime.scheduler_tick(conn, enqueue_callable=enqueue, scheduler_id="host:100", now=now)

    assert prune.await_count == 2
    prune.assert_any_await(
        conn,
        runtime_kind=scheduler_runtime.RUNTIME_KIND_WORKER,
        stale_before=now - timedelta(
            seconds=scheduler_runtime._runtime_stale_after_seconds(scheduler_runtime.RUNTIME_KIND_WORKER)
            + scheduler_runtime.settings.RUNTIME_HEARTBEAT_RETENTION_SECONDS,
        ),
    )
    prune.assert_any_await(
        conn,
        runtime_kind=scheduler_runtime.RUNTIME_KIND_SCHEDULER,
        stale_before=now - timedelta(
            seconds=scheduler_runtime._runtime_stale_after_seconds(scheduler_runtime.RUNTIME_KIND_SCHEDULER)
            + scheduler_runtime.settings.RUNTIME_HEARTBEAT_RETENTION_SECONDS,
        ),
    )


@pytest.mark.asyncio
async def test_scheduler_prunes_old_analytics_events_using_retention_days(monkeypatch):
    class _Conn:
        async def fetchval(self, *args, **kwargs):
            return 0

        def transaction(self):
            class _Tx:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

            return _Tx()

    conn = _Conn()
    enqueue = AsyncMock()
    prune_events = AsyncMock(return_value=17)

    monkeypatch.setattr(scheduler_runtime.settings, "ANALYTICS_EVENTS_RETENTION_DAYS", 90)
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "delete_stale_runtimes", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.analytics_service, "prune_old_events", prune_events)
    monkeypatch.setattr(scheduler_runtime.withdrawal_runtime_service, "schedule_auto_approve_jobs", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_orphaned_queued_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_due_retry_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_stale_running_jobs", AsyncMock(return_value=[]))

    await scheduler_runtime.scheduler_tick(conn, enqueue_callable=enqueue, scheduler_id="host:100", now=datetime.now(timezone.utc))

    prune_events.assert_awaited_once_with(conn, retention_days=90)


@pytest.mark.asyncio
async def test_scheduler_schedules_withdrawal_auto_approve_jobs_when_flag_enabled(monkeypatch):
    conn = object()
    enqueue = AsyncMock()
    schedule = AsyncMock(return_value=2)

    monkeypatch.setattr(scheduler_runtime.settings, "WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED", True)
    monkeypatch.setattr(scheduler_runtime.settings, "WITHDRAWAL_AUTO_APPROVE_LIMIT", "50.0")
    monkeypatch.setattr(scheduler_runtime.settings, "WITHDRAWAL_AUTO_APPROVE_BATCH_LIMIT", 25)
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "delete_stale_runtimes", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.withdrawal_runtime_service, "schedule_auto_approve_jobs", schedule)
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_orphaned_queued_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_due_retry_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_stale_running_jobs", AsyncMock(return_value=[]))

    await scheduler_runtime.scheduler_tick(conn, enqueue_callable=enqueue, scheduler_id="host:100", now=datetime.now(timezone.utc))

    schedule.assert_awaited_once_with(conn, auto_approve_limit="50.0", batch_limit=25)


@pytest.mark.asyncio
async def test_scheduler_lease_allows_only_one_active_scheduler_until_expiry(monkeypatch):
    conn = object()
    now = datetime.now(timezone.utc)
    redis = FakeRedisLease()
    tick = AsyncMock(return_value={"orphaned_enqueued": 0, "retry_enqueued": 0, "rescued_running": 0})
    heartbeat = AsyncMock()

    monkeypatch.setattr(scheduler_runtime, "refresh_scheduler_runtime_heartbeat", heartbeat)

    first = await scheduler_runtime.run_scheduler_iteration(
        conn,
        redis=redis,
        enqueue_callable=AsyncMock(),
        scheduler_id="host:100",
        lease_token="lease-1",
        now=now,
        tick_callable=tick,
    )
    second = await scheduler_runtime.run_scheduler_iteration(
        conn,
        redis=redis,
        enqueue_callable=AsyncMock(),
        scheduler_id="host:200",
        lease_token="lease-2",
        now=now,
        tick_callable=tick,
    )

    assert first == {"orphaned_enqueued": 0, "retry_enqueued": 0, "rescued_running": 0}
    assert second is None
    assert tick.await_count == 1
    heartbeat.assert_awaited_once_with(conn, scheduler_id="host:200", now=now, is_leader=False)

    redis.advance(scheduler_runtime._scheduler_lease_ttl_seconds() + 1)

    third = await scheduler_runtime.run_scheduler_iteration(
        conn,
        redis=redis,
        enqueue_callable=AsyncMock(),
        scheduler_id="host:200",
        lease_token="lease-2",
        now=now,
        tick_callable=tick,
    )

    assert third == {"orphaned_enqueued": 0, "retry_enqueued": 0, "rescued_running": 0}
    assert tick.await_count == 2


@pytest.mark.asyncio
async def test_scheduler_lease_release_is_fenced_to_owner_token():
    redis = FakeRedisLease()

    acquired = await scheduler_runtime.acquire_or_renew_scheduler_lease(
        redis,
        scheduler_id="host:100",
        lease_token="lease-1",
        ttl_seconds=30,
    )
    released_by_other = await scheduler_runtime.release_scheduler_lease(
        redis,
        scheduler_id="host:100",
        lease_token="wrong-token",
    )
    renewed = await scheduler_runtime.acquire_or_renew_scheduler_lease(
        redis,
        scheduler_id="host:100",
        lease_token="lease-1",
        ttl_seconds=30,
    )
    released_by_owner = await scheduler_runtime.release_scheduler_lease(
        redis,
        scheduler_id="host:100",
        lease_token="lease-1",
    )

    assert acquired is True
    assert released_by_other is False
    assert renewed is True
    assert released_by_owner is True


@pytest.mark.asyncio
async def test_scheduler_caps_stale_running_recovery_window_to_heartbeat_bound(monkeypatch):
    conn = object()
    enqueue = AsyncMock()
    now = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)
    find_stale = AsyncMock(return_value=[])

    monkeypatch.setattr(scheduler_runtime.settings, "WORKER_HEARTBEAT_INTERVAL_SECONDS", 15)
    monkeypatch.setattr(scheduler_runtime.settings, "STALE_RUNNING_TIMEOUT_SECONDS", 3600)
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(scheduler_runtime.runtime_heartbeat_repository, "delete_stale_runtimes", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.withdrawal_runtime_service, "schedule_auto_approve_jobs", AsyncMock(return_value=0))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_orphaned_queued_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_due_retry_jobs", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler_runtime.job_repository, "find_stale_running_jobs", find_stale)

    await scheduler_runtime.scheduler_tick(conn, enqueue_callable=enqueue, scheduler_id="host:100", now=now)

    find_stale.assert_awaited_once_with(
        conn,
        stale_before=now - timedelta(seconds=45),
    )
