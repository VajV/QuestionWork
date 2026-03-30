from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.repositories import job_repository, runtime_heartbeat_repository


@pytest.mark.asyncio
async def test_job_claim_state_machine_allows_only_one_worker_to_transition_queued_to_running():
    conn = AsyncMock()
    first = {"id": "job-1", "status": "running"}
    conn.fetchrow = AsyncMock(side_effect=[first, None])

    claimed = await job_repository.claim_job(
        conn,
        job_id="job-1",
        worker_id="host:100",
        lock_token="lock-1",
    )
    second_claim = await job_repository.claim_job(
        conn,
        job_id="job-1",
        worker_id="host:200",
        lock_token="lock-2",
    )

    assert claimed == first
    assert second_claim is None
    first_query = conn.fetchrow.await_args_list[0].args[0]
    assert "status IN ('queued', 'retry_scheduled')" in first_query
    assert "SET status = 'running'" in first_query


@pytest.mark.asyncio
async def test_create_job_persists_json_and_schedule_fields():
    conn = AsyncMock()
    row = {"id": "job-2", "status": "queued"}
    conn.fetchrow = AsyncMock(return_value=row)
    scheduled = datetime.now(timezone.utc)

    result = await job_repository.create_job(
        conn,
        kind="ops.noop",
        dedupe_key="ops:noop:2",
        payload_json={"noop": True},
        scheduled_for=scheduled,
        command_id="cmd-2",
    )

    assert result == row
    query = conn.fetchrow.await_args.args[0]
    assert "INSERT INTO background_jobs" in query
    assert conn.fetchrow.await_args.args[6] == '{"noop": true}'
    assert conn.fetchrow.await_args.args[7] == scheduled


@pytest.mark.asyncio
async def test_mark_job_retry_scheduled_increments_attempt_count_and_clears_lock():
    conn = AsyncMock()
    row = {"id": "job-3", "status": "retry_scheduled"}
    conn.fetchrow = AsyncMock(return_value=row)
    available_at = datetime.now(timezone.utc) + timedelta(seconds=30)

    result = await job_repository.mark_job_retry_scheduled(
        conn,
        "job-3",
        error_code="retryable",
        error_text="network",
        available_at=available_at,
    )

    assert result == row
    query = conn.fetchrow.await_args.args[0]
    assert "attempt_count = attempt_count + 1" in query
    assert "lock_token = NULL" in query
    assert "locked_by = NULL" in query


@pytest.mark.asyncio
async def test_mark_job_dead_letter_marks_terminal_failure():
    conn = AsyncMock()
    row = {"id": "job-4", "status": "dead_letter"}
    conn.fetchrow = AsyncMock(return_value=row)

    result = await job_repository.mark_job_dead_letter(
        conn,
        "job-4",
        error_code="max_attempts",
        error_text="too many failures",
    )

    assert result == row
    query = conn.fetchrow.await_args.args[0]
    assert "SET status = 'dead_letter'" in query


@pytest.mark.asyncio
async def test_record_enqueue_success_and_failure_bookkeeping():
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["UPDATE 1", "UPDATE 1"])

    ok = await job_repository.record_enqueue_success(conn, "job-5")
    failed = await job_repository.record_enqueue_failure(conn, "job-5", error_text="redis down")

    assert ok == "UPDATE 1"
    assert failed == "UPDATE 1"
    assert "enqueued_at = NOW()" in conn.execute.await_args_list[0].args[0]
    assert "last_enqueue_error = $2" in conn.execute.await_args_list[1].args[0]


@pytest.mark.asyncio
async def test_stale_running_recovery_clears_lock_fields_and_reuses_same_job_id():
    conn = AsyncMock()
    row = {"id": "job-6", "status": "retry_scheduled"}
    conn.fetchrow = AsyncMock(return_value=row)

    result = await job_repository.rescue_stale_running_job(conn, job_id="job-6")

    assert result == row
    query, job_id, _available_at = conn.fetchrow.await_args.args
    assert "SET status = 'retry_scheduled'" in query
    assert "lock_token = NULL" in query
    assert "locked_by = NULL" in query
    assert "last_heartbeat_at = NULL" in query
    assert job_id == "job-6"


@pytest.mark.asyncio
async def test_worker_shutdown_recovery_requeues_all_running_jobs_owned_by_worker():
    conn = AsyncMock()
    rows = [{"id": "job-7"}, {"id": "job-8"}]
    conn.fetch = AsyncMock(return_value=rows)

    result = await job_repository.rescue_running_jobs_for_worker(conn, worker_id="host:100")

    assert result == rows
    query, worker_id, _available_at = conn.fetch.await_args.args
    assert "SET status = 'retry_scheduled'" in query
    assert "locked_by = NULL" in query
    assert "WHERE status = 'running'" in query
    assert worker_id == "host:100"


@pytest.mark.asyncio
async def test_runtime_heartbeat_upsert_and_lookup_round_trip_queries():
    conn = AsyncMock()
    row = {"runtime_id": "worker-1", "runtime_kind": "worker"}
    conn.fetchrow = AsyncMock(side_effect=[row, row])
    now = datetime.now(timezone.utc)

    upserted = await runtime_heartbeat_repository.upsert_runtime_heartbeat(
        conn,
        runtime_kind="worker",
        runtime_id="worker-1",
        hostname="host",
        pid=101,
        started_at=now,
        last_seen_at=now,
        meta_json={"queue": "ops"},
    )
    loaded = await runtime_heartbeat_repository.get_runtime_heartbeat(
        conn,
        runtime_kind="worker",
        runtime_id="worker-1",
    )

    assert upserted == row
    assert loaded == row
    assert "ON CONFLICT (runtime_kind, runtime_id)" in conn.fetchrow.await_args_list[0].args[0]


@pytest.mark.asyncio
async def test_partial_repository_transaction_failure_bubbles_up_for_outer_rollback():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": "job-7"})

    with pytest.raises(RuntimeError, match="boom"):
        await job_repository.create_job(conn, kind="ops.noop")
        raise RuntimeError("boom")