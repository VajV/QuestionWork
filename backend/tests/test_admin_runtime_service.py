from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.services import admin_runtime_service


class _FrozenDateTime(datetime):
    _now = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls._now.replace(tzinfo=None)
        return cls._now.astimezone(tz)


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    async def fetch(self, *_args, **_kwargs):
        return list(self._rows)


class _Txn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _ReplayConn:
    def __init__(self, job):
        self.job = job

    async def fetchrow(self, *_args, **_kwargs):
        return self.job

    def transaction(self):
        return _Txn()


@pytest.mark.asyncio
async def test_list_runtime_heartbeats_exposes_leadership_and_kind_counts(monkeypatch):
    now = _FrozenDateTime._now
    rows = [
        {
            "id": "hb-1",
            "runtime_kind": "scheduler",
            "runtime_id": "host:100",
            "hostname": "host",
            "pid": 100,
            "started_at": now - timedelta(seconds=90),
            "last_seen_at": now - timedelta(seconds=5),
            "meta_json": {"is_leader": True, "lease_ttl_seconds": 30, "poll_interval_seconds": 10},
        },
        {
            "id": "hb-2",
            "runtime_kind": "worker",
            "runtime_id": "host:200",
            "hostname": "host",
            "pid": 200,
            "started_at": now - timedelta(seconds=70),
            "last_seen_at": now - timedelta(seconds=4),
            "meta_json": {"queue": "ops"},
        },
        {
            "id": "hb-3",
            "runtime_kind": "worker",
            "runtime_id": "host:201",
            "hostname": "host",
            "pid": 201,
            "started_at": now - timedelta(seconds=400),
            "last_seen_at": now - timedelta(seconds=120),
            "meta_json": {"queue": "ops"},
        },
    ]

    monkeypatch.setattr(admin_runtime_service, "datetime", _FrozenDateTime)

    result = await admin_runtime_service.list_runtime_heartbeats(
        _FakeConn(rows),
        limit=10,
        active_only=False,
    )

    assert result["active_schedulers"] == 1
    assert result["active_workers"] == 1
    assert result["stale_workers"] == 1
    assert result["stale_schedulers"] == 0
    assert result["leader_count"] == 1
    assert result["leader_runtime_id"] == "host:100"

    scheduler_entry = next(item for item in result["runtimes"] if item["runtime_kind"] == "scheduler")
    worker_entry = next(item for item in result["runtimes"] if item["runtime_id"] == "host:200")

    assert scheduler_entry["heartbeat_interval_seconds"] == 10
    assert scheduler_entry["started_age_seconds"] == 90
    assert scheduler_entry["is_leader"] is True
    assert scheduler_entry["lease_ttl_seconds"] == 30
    assert scheduler_entry["lease_expires_in_seconds"] == 25
    assert worker_entry["queue_name"] == "ops"
    assert worker_entry["heartbeat_interval_seconds"] == 15


@pytest.mark.asyncio
async def test_list_runtime_heartbeats_active_only_filters_stale_rows(monkeypatch):
    now = _FrozenDateTime._now
    rows = [
        {
            "id": "hb-1",
            "runtime_kind": "worker",
            "runtime_id": "host:200",
            "hostname": "host",
            "pid": 200,
            "started_at": now - timedelta(seconds=70),
            "last_seen_at": now - timedelta(seconds=4),
            "meta_json": {"queue": "ops"},
        },
        {
            "id": "hb-2",
            "runtime_kind": "worker",
            "runtime_id": "host:201",
            "hostname": "host",
            "pid": 201,
            "started_at": now - timedelta(seconds=400),
            "last_seen_at": now - timedelta(seconds=120),
            "meta_json": {"queue": "ops"},
        },
    ]

    monkeypatch.setattr(admin_runtime_service, "datetime", _FrozenDateTime)

    result = await admin_runtime_service.list_runtime_heartbeats(
        _FakeConn(rows),
        limit=10,
        active_only=True,
    )

    assert result["total"] == 1
    assert result["stale_total"] == 1
    assert result["runtimes"][0]["runtime_id"] == "host:200"


@pytest.mark.asyncio
async def test_list_runtime_heartbeats_defaults_to_active_only_and_hides_stale_rows(monkeypatch):
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    stale_worker_at = now - timedelta(seconds=200)
    active_worker_at = now - timedelta(seconds=5)
    rows = [
        {
            "id": "worker-stale",
            "runtime_kind": "worker",
            "runtime_id": "host:1",
            "hostname": "host",
            "pid": 1,
            "started_at": now - timedelta(minutes=10),
            "last_seen_at": stale_worker_at,
            "meta_json": {"queue": "ops"},
        },
        {
            "id": "worker-active",
            "runtime_kind": "worker",
            "runtime_id": "host:2",
            "hostname": "host",
            "pid": 2,
            "started_at": now - timedelta(minutes=3),
            "last_seen_at": active_worker_at,
            "meta_json": {"queue": "ops"},
        },
    ]

    class _Now(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(admin_runtime_service, "datetime", _Now)

    result = await admin_runtime_service.list_runtime_heartbeats(_FakeConn(rows), runtime_kind="worker", limit=10)

    assert result["active_only"] is True
    assert result["stale_total"] == 1
    assert result["total"] == 1
    assert [item["id"] for item in result["runtimes"]] == ["worker-active"]


@pytest.mark.asyncio
async def test_list_runtime_heartbeats_can_include_stale_rows_when_active_only_disabled(monkeypatch):
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "id": "scheduler-active",
            "runtime_kind": "scheduler",
            "runtime_id": "host:10",
            "hostname": "host",
            "pid": 10,
            "started_at": now - timedelta(minutes=2),
            "last_seen_at": now - timedelta(seconds=5),
            "meta_json": {"poll_interval_seconds": 10},
        },
        {
            "id": "scheduler-stale",
            "runtime_kind": "scheduler",
            "runtime_id": "host:11",
            "hostname": "host",
            "pid": 11,
            "started_at": now - timedelta(minutes=20),
            "last_seen_at": now - timedelta(seconds=90),
            "meta_json": {"poll_interval_seconds": 10},
        },
    ]

    class _Now(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(admin_runtime_service, "datetime", _Now)

    result = await admin_runtime_service.list_runtime_heartbeats(
        _FakeConn(rows),
        runtime_kind="scheduler",
        limit=10,
        active_only=False,
    )

    assert result["active_only"] is False
    assert result["stale_total"] == 1
    assert result["total"] == 2
    assert {item["id"] for item in result["runtimes"]} == {"scheduler-active", "scheduler-stale"}


@pytest.mark.asyncio
async def test_prune_runtime_heartbeats_uses_stale_threshold_plus_retention(monkeypatch):
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    conn = object()

    class _Now(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(admin_runtime_service, "datetime", _Now)
    delete_stale = AsyncMock(return_value=2)
    monkeypatch.setattr(admin_runtime_service.runtime_heartbeat_repository, "delete_stale_runtimes", delete_stale)

    result = await admin_runtime_service.prune_runtime_heartbeats(
        conn,
        runtime_kind="worker",
        stale_only=True,
        retention_seconds=0,
    )

    assert result["deleted_count"] == 2
    delete_stale.assert_awaited_once_with(
        conn,
        runtime_kind="worker",
        stale_before=now - timedelta(seconds=admin_runtime_service._runtime_stale_after_seconds("worker")),
    )


@pytest.mark.asyncio
async def test_requeue_job_resets_terminal_job_and_enqueues(monkeypatch):
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    job = {
        "id": "job-1",
        "status": "dead_letter",
        "attempt_count": 5,
        "queue_name": "ops",
        "last_error_code": "ProviderError",
        "command_id": "cmd-1",
        "request_id": "req-1",
        "trace_id": "trace-1",
    }
    replayed = {
        **job,
        "status": "retry_scheduled",
    }

    class _Now(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    redis = AsyncMock()
    monkeypatch.setattr(admin_runtime_service, "datetime", _Now)
    monkeypatch.setattr(admin_runtime_service.job_repository, "requeue_terminal_job", AsyncMock(return_value=replayed))
    monkeypatch.setattr(admin_runtime_service.command_repository, "reset_command_for_replay", AsyncMock())
    monkeypatch.setattr(admin_runtime_service.admin_service, "log_admin_action", AsyncMock())
    monkeypatch.setattr(admin_runtime_service, "create_arq_pool", AsyncMock(return_value=redis))
    monkeypatch.setattr(admin_runtime_service, "enqueue_job_message", AsyncMock(return_value=None))
    monkeypatch.setattr(admin_runtime_service.job_repository, "record_enqueue_success", AsyncMock(return_value="UPDATE 1"))
    monkeypatch.setattr(admin_runtime_service.job_repository, "record_enqueue_failure", AsyncMock(return_value="UPDATE 1"))

    conn = _ReplayConn(job)

    result = await admin_runtime_service.requeue_job(
        conn,
        job_id="job-1",
        admin_id="admin-1",
        reason="provider fixed",
        request_ip="127.0.0.1",
    )

    assert result is not None
    assert result["job_id"] == "job-1"
    assert result["previous_status"] == "dead_letter"
    assert result["status"] == "retry_scheduled"
    assert result["enqueued"] is True
    admin_runtime_service.command_repository.reset_command_for_replay.assert_awaited_once_with(conn, "cmd-1")


@pytest.mark.asyncio
async def test_requeue_job_rejects_non_terminal_status(monkeypatch):
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    job = {
        "id": "job-2",
        "status": "running",
        "attempt_count": 1,
        "queue_name": "ops",
        "last_error_code": None,
        "command_id": None,
        "request_id": None,
        "trace_id": None,
    }

    class _Now(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(admin_runtime_service, "datetime", _Now)

    with pytest.raises(ValueError, match="Only failed or dead-letter jobs can be requeued manually"):
        await admin_runtime_service.requeue_job(
            _ReplayConn(job),
            job_id="job-2",
            admin_id="admin-1",
        )
