from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from decimal import Decimal

from app.jobs.handlers.withdrawal_auto_approve import WithdrawalAutoApproveHandler
from app.services import withdrawal_runtime_service


@pytest.mark.asyncio
async def test_schedule_auto_approve_jobs_creates_ops_jobs_for_eligible_withdrawals(monkeypatch):
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"id": "tx-1", "user_id": "user-1", "amount": "25.00", "currency": "RUB"},
            {"id": "tx-2", "user_id": "user-2", "amount": "30.00", "currency": "RUB"},
        ]
    )
    create_job = AsyncMock()
    monkeypatch.setattr(withdrawal_runtime_service.job_repository, "create_job", create_job)

    created = await withdrawal_runtime_service.schedule_auto_approve_jobs(
        conn,
        auto_approve_limit="50.0",
        batch_limit=10,
    )

    assert created == 2
    assert "NOT EXISTS" in conn.fetch.await_args.args[0]
    assert create_job.await_count == 2
    first_kwargs = create_job.await_args_list[0].kwargs
    assert first_kwargs["kind"] == withdrawal_runtime_service.WITHDRAWAL_AUTO_APPROVE_KIND
    assert first_kwargs["queue_name"] == "ops"
    assert first_kwargs["dedupe_key"] == "withdrawal:auto-approve:tx-1"
    assert first_kwargs["entity_type"] == "transaction"
    assert first_kwargs["entity_id"] == "tx-1"
    assert conn.fetch.await_args.args[1] == Decimal("50.0")


@pytest.mark.asyncio
async def test_schedule_auto_approve_jobs_skips_duplicate_dedupe_key_insert_races(monkeypatch):
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"id": "tx-1", "user_id": "user-1", "amount": "25.00", "currency": "RUB"},
            {"id": "tx-2", "user_id": "user-2", "amount": "30.00", "currency": "RUB"},
        ]
    )
    duplicate_error = asyncpg.UniqueViolationError("duplicate dedupe key")
    create_job = AsyncMock(side_effect=[duplicate_error, {"id": "job-2"}])
    monkeypatch.setattr(withdrawal_runtime_service.job_repository, "create_job", create_job)

    created = await withdrawal_runtime_service.schedule_auto_approve_jobs(
        conn,
        auto_approve_limit="50.0",
        batch_limit=10,
    )

    assert created == 1
    assert create_job.await_count == 2


@pytest.mark.asyncio
async def test_withdrawal_auto_approve_handler_approves_pending_withdrawal_and_links_job(monkeypatch):
    conn = AsyncMock()
    txn = AsyncMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)
    conn.fetchrow = AsyncMock(
        return_value={
            "id": "tx-1",
            "user_id": "user-1",
            "type": "withdrawal",
            "status": "pending",
            "amount": "25.00",
            "currency": "RUB",
        }
    )
    conn.fetchval = AsyncMock(return_value=True)
    approve = AsyncMock(return_value={"user_id": "user-1", "amount": "25.00", "currency": "RUB"})
    notify = AsyncMock()
    monkeypatch.setattr("app.jobs.handlers.withdrawal_auto_approve.admin_service.approve_withdrawal", approve)
    monkeypatch.setattr("app.jobs.handlers.withdrawal_auto_approve.notification_service.create_notification", notify)

    handler = WithdrawalAutoApproveHandler()
    context = MagicMock(job_id="job-1", request_id="req-1", trace_id="trace-1", worker_id="host:100")

    result = await handler.execute(conn, {"transaction_id": "tx-1"}, context)

    assert result["status"] == "succeeded"
    approve.assert_awaited_once_with(
        conn,
        transaction_id="tx-1",
        admin_id="system",
        ip_address="127.0.0.1 (scheduler-auto-approve)",
        job_id="job-1",
        request_id="req-1",
        trace_id="trace-1",
    )
    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_withdrawal_auto_approve_handler_ignores_non_pending_transactions():
    conn = AsyncMock()
    txn = AsyncMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)
    conn.fetchrow = AsyncMock(
        return_value={
            "id": "tx-1",
            "user_id": "user-1",
            "type": "withdrawal",
            "status": "completed",
            "amount": "25.00",
            "currency": "RUB",
        }
    )

    handler = WithdrawalAutoApproveHandler()
    context = MagicMock(job_id="job-1", request_id=None, trace_id=None, worker_id="host:100")

    result = await handler.execute(conn, {"transaction_id": "tx-1"}, context)

    assert result == {
        "kind": withdrawal_runtime_service.WITHDRAWAL_AUTO_APPROVE_KIND,
        "status": "ignored",
        "reason": "already-completed",
        "transaction_id": "tx-1",
        "job_id": "job-1",
    }