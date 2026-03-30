from datetime import datetime, timezone
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.jobs import arq as arq_runtime
from app.jobs.context import JobContext
from app.jobs.enums import QUEUE_OPS
from app.jobs.handlers.ops_noop import OpsNoopHandler
from app.jobs.registry import get_handler
from app.jobs import worker as worker_runtime


@pytest.mark.asyncio
async def test_arq_settings_are_built_from_config_predictably():
    settings = arq_runtime.build_redis_settings("redis://localhost:6379/4")

    assert settings.host == "localhost"
    assert settings.port == 6379
    assert settings.database == 4


def test_registry_returns_the_noop_handler_for_its_kind():
    handler = get_handler("ops.noop")

    assert isinstance(handler, OpsNoopHandler)
    assert handler.kind == "ops.noop"
    assert handler.queue_name == QUEUE_OPS


@pytest.mark.asyncio
async def test_noop_handler_returns_deterministic_payload_for_smoke_verification():
    handler = OpsNoopHandler()
    context = JobContext(worker_id="host:100", trace_id="trace-1", request_id="req-1")

    result = await handler.execute(None, {"hello": "world"}, context)

    assert result == {
        "kind": "ops.noop",
        "worker_id": "host:100",
        "trace_id": "trace-1",
        "request_id": "req-1",
        "payload": {"hello": "world"},
    }


def test_validate_job_message_allows_only_job_and_trace_metadata():
    message = arq_runtime.validate_job_message({"job_id": "job-1", "trace_id": "t", "request_id": "r"})
    assert message["job_id"] == "job-1"

    uuid_message = arq_runtime.validate_job_message({"job_id": uuid4()})
    assert isinstance(uuid_message["job_id"], str)

    with pytest.raises(ValueError, match="Unsupported job payload keys"):
        arq_runtime.validate_job_message({"job_id": "job-1", "extra": True})


@pytest.mark.asyncio
async def test_enqueue_job_message_uses_arq_function_name_and_queue():
    redis = AsyncMock()
    redis.enqueue_job = AsyncMock(return_value="queued")

    result = await arq_runtime.enqueue_job_message(
        redis,
        job_id="job-1",
        function_name="process_job_message",
        queue_name="ops",
        trace_id="trace-1",
        request_id="req-1",
    )

    assert result == "queued"
    args = redis.enqueue_job.await_args
    assert args.args[0] == "process_job_message"
    assert args.args[1]["job_id"] == "job-1"
    assert args.kwargs["_queue_name"] == "ops"


@pytest.mark.asyncio
async def test_worker_claims_job_writes_lock_token_attempt_and_completes_noop(monkeypatch):
    conn = object()
    now = datetime.now(timezone.utc)
    job_row = {
        "id": "job-1",
        "kind": "ops.noop",
        "payload_json": {"ok": True},
        "attempt_count": 0,
        "max_attempts": 1,
        "command_id": "cmd-1",
        "queue_name": "ops",
    }
    claimed_row = dict(job_row, status="running")

    get_job = AsyncMock(return_value=job_row)
    claim_job = AsyncMock(return_value=claimed_row)
    insert_attempt = AsyncMock()
    mark_job_succeeded = AsyncMock()
    mark_cmd_running = AsyncMock()
    mark_cmd_succeeded = AsyncMock()
    upsert_heartbeat = AsyncMock()

    monkeypatch.setattr(worker_runtime.job_repository, "get_job_by_id", get_job)
    monkeypatch.setattr(worker_runtime.job_repository, "claim_job", claim_job)
    monkeypatch.setattr(worker_runtime.job_repository, "insert_attempt", insert_attempt)
    monkeypatch.setattr(worker_runtime.job_repository, "mark_job_succeeded", mark_job_succeeded)
    monkeypatch.setattr(worker_runtime.command_repository, "mark_command_running", mark_cmd_running)
    monkeypatch.setattr(worker_runtime.command_repository, "mark_command_succeeded", mark_cmd_succeeded)
    monkeypatch.setattr(worker_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", upsert_heartbeat)
    monkeypatch.setattr(worker_runtime, "make_lock_token", lambda: "lock-123")

    result = await worker_runtime.execute_job_payload(conn, {"job_id": "job-1", "trace_id": "t-1", "request_id": "r-1"}, worker_id="host:100")

    assert result["status"] == "succeeded"
    claim_kwargs = claim_job.await_args.kwargs
    assert claim_kwargs["lock_token"] == "lock-123"
    assert claim_kwargs["worker_id"] == "host:100"
    insert_kwargs = insert_attempt.await_args.kwargs
    assert insert_kwargs["attempt_no"] == 1
    mark_cmd_running.assert_awaited_once_with(conn, "cmd-1")
    mark_job_succeeded.assert_awaited_once_with(conn, "job-1")
    mark_cmd_succeeded.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_decodes_jsonb_payload_strings_before_handler_execution(monkeypatch):
    conn = object()
    job_row = {
        "id": "job-json",
        "kind": "ops.noop",
        "payload_json": '{"ok": true, "source": "jsonb"}',
        "attempt_count": 0,
        "max_attempts": 1,
        "command_id": None,
        "queue_name": "ops",
    }
    claimed_row = dict(job_row, status="running")
    observed_payloads: list[dict] = []

    class CapturingHandler(OpsNoopHandler):
        async def execute(self, conn, payload, context):
            observed_payloads.append(payload)
            return await super().execute(conn, payload, context)

    monkeypatch.setattr(worker_runtime.job_repository, "get_job_by_id", AsyncMock(return_value=job_row))
    monkeypatch.setattr(worker_runtime.job_repository, "claim_job", AsyncMock(return_value=claimed_row))
    monkeypatch.setattr(worker_runtime.job_repository, "insert_attempt", AsyncMock())
    monkeypatch.setattr(worker_runtime.job_repository, "mark_job_succeeded", AsyncMock())
    monkeypatch.setattr(worker_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(worker_runtime, "get_handler", lambda kind: CapturingHandler())

    result = await worker_runtime.execute_job_payload(conn, {"job_id": "job-json"}, worker_id="host:105")

    assert result["status"] == "succeeded"
    assert observed_payloads == [{"ok": True, "source": "jsonb"}]


@pytest.mark.asyncio
async def test_worker_records_retry_scheduling_on_retryable_failure(monkeypatch):
    conn = object()
    job_row = {
        "id": "job-2",
        "kind": "ops.noop",
        "payload_json": {},
        "attempt_count": 0,
        "max_attempts": 3,
        "command_id": "cmd-2",
        "queue_name": "ops",
    }
    claimed_row = dict(job_row, status="running")

    class RetryableHandler(OpsNoopHandler):
        def is_retryable(self, error: Exception) -> bool:
            return True

        def backoff_seconds(self, attempt_no: int, error_code: str | None) -> int:
            return 30

        async def execute(self, conn, payload, context):
            raise RuntimeError("retry me")

    monkeypatch.setattr(worker_runtime.job_repository, "get_job_by_id", AsyncMock(return_value=job_row))
    monkeypatch.setattr(worker_runtime.job_repository, "claim_job", AsyncMock(return_value=claimed_row))
    monkeypatch.setattr(worker_runtime.job_repository, "insert_attempt", AsyncMock())
    retry_mark = AsyncMock()
    monkeypatch.setattr(worker_runtime.job_repository, "mark_job_retry_scheduled", retry_mark)
    monkeypatch.setattr(worker_runtime.command_repository, "mark_command_running", AsyncMock())
    mark_cmd_failed = AsyncMock()
    monkeypatch.setattr(worker_runtime.command_repository, "mark_command_failed", mark_cmd_failed)
    monkeypatch.setattr(worker_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(worker_runtime, "get_handler", lambda kind: RetryableHandler())

    result = await worker_runtime.execute_job_payload(conn, {"job_id": "job-2"}, worker_id="host:101")

    assert result["status"] == "retryable-failure"
    retry_mark.assert_awaited_once()
    mark_cmd_failed.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_marks_terminal_failure_without_retry(monkeypatch):
    conn = object()
    job_row = {
        "id": "job-3",
        "kind": "ops.noop",
        "payload_json": {},
        "attempt_count": 0,
        "max_attempts": 3,
        "command_id": "cmd-3",
        "queue_name": "ops",
    }
    claimed_row = dict(job_row, status="running")

    class FailingHandler(OpsNoopHandler):
        async def execute(self, conn, payload, context):
            raise ValueError("stop")

    monkeypatch.setattr(worker_runtime.job_repository, "get_job_by_id", AsyncMock(return_value=job_row))
    monkeypatch.setattr(worker_runtime.job_repository, "claim_job", AsyncMock(return_value=claimed_row))
    monkeypatch.setattr(worker_runtime.job_repository, "insert_attempt", AsyncMock())
    mark_job_failed = AsyncMock()
    monkeypatch.setattr(worker_runtime.job_repository, "mark_job_failed", mark_job_failed)
    monkeypatch.setattr(worker_runtime.command_repository, "mark_command_running", AsyncMock())
    mark_cmd_failed = AsyncMock()
    monkeypatch.setattr(worker_runtime.command_repository, "mark_command_failed", mark_cmd_failed)
    monkeypatch.setattr(worker_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(worker_runtime, "get_handler", lambda kind: FailingHandler())

    result = await worker_runtime.execute_job_payload(conn, {"job_id": "job-3"}, worker_id="host:102")

    assert result["status"] == "failed"
    mark_job_failed.assert_awaited_once()
    mark_cmd_failed.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_marks_dead_letter_when_max_attempts_reached(monkeypatch):
    conn = object()
    job_row = {
        "id": "job-4",
        "kind": "ops.noop",
        "payload_json": {},
        "attempt_count": 0,
        "max_attempts": 1,
        "command_id": "cmd-4",
        "queue_name": "ops",
    }
    claimed_row = dict(job_row, status="running")

    class RetryableHandler(OpsNoopHandler):
        def is_retryable(self, error: Exception) -> bool:
            return True

        async def execute(self, conn, payload, context):
            raise RuntimeError("retry me")

    monkeypatch.setattr(worker_runtime.job_repository, "get_job_by_id", AsyncMock(return_value=job_row))
    monkeypatch.setattr(worker_runtime.job_repository, "claim_job", AsyncMock(return_value=claimed_row))
    monkeypatch.setattr(worker_runtime.job_repository, "insert_attempt", AsyncMock())
    dead_letter = AsyncMock()
    monkeypatch.setattr(worker_runtime.job_repository, "mark_job_dead_letter", dead_letter)
    monkeypatch.setattr(worker_runtime.command_repository, "mark_command_running", AsyncMock())
    monkeypatch.setattr(worker_runtime.command_repository, "mark_command_failed", AsyncMock())
    monkeypatch.setattr(worker_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(worker_runtime, "get_handler", lambda kind: RetryableHandler())

    result = await worker_runtime.execute_job_payload(conn, {"job_id": "job-4"}, worker_id="host:103")

    assert result["status"] == "retryable-failure"
    dead_letter.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_job_message_acquires_db_connection_from_pool(monkeypatch):
    conn = object()
    execute_job_payload = AsyncMock(return_value={"status": "succeeded", "job_id": "job-5"})

    @asynccontextmanager
    async def fake_acquire_db_connection():
        yield conn

    monkeypatch.setattr(worker_runtime, "acquire_db_connection", fake_acquire_db_connection)
    monkeypatch.setattr(worker_runtime, "execute_job_payload", execute_job_payload)

    result = await worker_runtime.process_job_message({"worker_id": "host:104"}, {"job_id": "job-5"})

    assert result == {"status": "succeeded", "job_id": "job-5"}
    execute_job_payload.assert_awaited_once_with(conn, {"job_id": "job-5"}, worker_id="host:104")


@pytest.mark.asyncio
async def test_worker_passes_claimed_job_id_into_handler_context(monkeypatch):
    conn = object()
    job_row = {
        "id": "job-ctx",
        "kind": "ops.noop",
        "payload_json": {},
        "attempt_count": 0,
        "max_attempts": 1,
        "command_id": None,
        "queue_name": "ops",
    }
    claimed_row = dict(job_row, status="running")

    observed_contexts: list[JobContext] = []

    class CapturingHandler(OpsNoopHandler):
        async def execute(self, conn, payload, context):
            observed_contexts.append(context)
            return await super().execute(conn, payload, context)

    monkeypatch.setattr(worker_runtime.job_repository, "get_job_by_id", AsyncMock(return_value=job_row))
    monkeypatch.setattr(worker_runtime.job_repository, "claim_job", AsyncMock(return_value=claimed_row))
    monkeypatch.setattr(worker_runtime.job_repository, "insert_attempt", AsyncMock())
    monkeypatch.setattr(worker_runtime.job_repository, "mark_job_succeeded", AsyncMock())
    monkeypatch.setattr(worker_runtime.runtime_heartbeat_repository, "upsert_runtime_heartbeat", AsyncMock())
    monkeypatch.setattr(worker_runtime, "get_handler", lambda kind: CapturingHandler())

    result = await worker_runtime.execute_job_payload(conn, {"job_id": "job-ctx"}, worker_id="host:201")

    assert result["status"] == "succeeded"
    assert observed_contexts[0].job_id == "job-ctx"


@pytest.mark.asyncio
async def test_worker_shutdown_releases_running_jobs_before_pool_close(monkeypatch):
    conn = object()
    released_jobs = [{"id": "job-1"}, {"id": "job-2"}]
    rescue = AsyncMock(return_value=released_jobs)
    close_pool = AsyncMock()

    @asynccontextmanager
    async def fake_acquire_db_connection():
        yield conn

    monkeypatch.setattr(worker_runtime, "acquire_db_connection", fake_acquire_db_connection)
    monkeypatch.setattr(worker_runtime.job_repository, "rescue_running_jobs_for_worker", rescue)
    monkeypatch.setattr(worker_runtime, "close_db_pool", close_pool)

    await worker_runtime.worker_shutdown({"worker_id": "host:300"})

    rescue.assert_awaited_once_with(conn, worker_id="host:300")
    close_pool.assert_awaited_once()