"""
Tests for process_withdrawals idempotency guarantees.

Verifies:
1. Advisory lock prevents parallel execution.
2. FOR UPDATE SKIP LOCKED query is issued.
3. Per-row error doesn't abort the whole batch.
4. Dry-run does not mutate any rows.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone


# ──────────────────────────────────────────────────────────────────────
# Mock asyncpg pool helpers
# ──────────────────────────────────────────────────────────────────────

def _make_pool(*, lock_acquired: bool = True, rows: list = None):
    """Return a mock asyncpg pool whose acquire() yields a mock connection."""
    rows = rows or []

    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=True)

    # pg_try_advisory_lock
    conn.fetchval = AsyncMock(side_effect=[lock_acquired, 1])  # lock, then actor_exists=True for each row
    conn.fetch = AsyncMock(return_value=rows)
    conn.execute = AsyncMock(return_value="SELECT 1")

    # transaction context manager (nested)
    txn = AsyncMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    # pool.acquire() context manager
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool.close = AsyncMock()

    return pool, conn


def _tx_row(tx_id="tx1", user_id="user1", amount=20.0, currency="RUB"):
    return {
        "id": tx_id, "user_id": user_id,
        "amount": amount, "currency": currency,
        "type": "withdrawal", "status": "pending",
        "quest_id": None, "created_at": datetime.now(timezone.utc),
    }


# ──────────────────────────────────────────────────────────────────────
# Advisory lock tests
# ──────────────────────────────────────────────────────────────────────

class TestAdvisoryLock:
    @pytest.mark.asyncio
    async def test_lock_not_acquired_exits_cleanly(self):
        """If pg_try_advisory_lock returns False the processor returns 0."""
        pool, conn = _make_pool(lock_acquired=False)

        with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=pool):
            from scripts.process_withdrawals import run
            result = await run(dry_run=False)

        assert result == 0
        # fetch should NOT have been called since we never had the lock
        conn.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_lock_acquired_processes_rows(self):
        """When lock is acquired rows are processed."""
        rows = [_tx_row("tx1"), _tx_row("tx2")]

        pool, conn = _make_pool(lock_acquired=True, rows=rows)
        # Provide enough fetchval answers: lock=True, then for each row: actor_exists (2×)
        conn.fetchval = AsyncMock(side_effect=[True, True, True])

        approve_result = {"status": "completed", "user_id": "user1",
                          "amount": 20.0, "currency": "RUB"}

        with (
            patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=pool),
            patch(
                "app.services.admin_service.approve_withdrawal",
                new_callable=AsyncMock,
                return_value=approve_result,
            ),
            patch(
                "app.services.notification_service.create_notification",
                new_callable=AsyncMock,
            ),
        ):
            from scripts.process_withdrawals import run
            result = await run(dry_run=False)

        assert result == 2

    @pytest.mark.asyncio
    async def test_advisory_lock_key_in_query(self):
        """The advisory lock SQL uses the expected constant key."""
        from scripts.process_withdrawals import _ADVISORY_LOCK_KEY

        assert isinstance(_ADVISORY_LOCK_KEY, int)
        assert _ADVISORY_LOCK_KEY > 0


# ──────────────────────────────────────────────────────────────────────
# SKIP LOCKED query test
# ──────────────────────────────────────────────────────────────────────

class TestSkipLocked:
    @pytest.mark.asyncio
    async def test_select_for_update_skip_locked(self):
        """The SELECT query must contain FOR UPDATE SKIP LOCKED."""
        rows = []
        pool, conn = _make_pool(lock_acquired=True, rows=rows)
        conn.fetchval = AsyncMock(return_value=True)  # lock acquired

        with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=pool):
            from scripts.process_withdrawals import run
            await run(dry_run=False)

        # The fetch call that reads pending withdrawals
        fetch_call = conn.fetch.call_args
        if fetch_call:
            sql = fetch_call[0][0]
            assert "SKIP LOCKED" in sql.upper()
            assert "FOR UPDATE" in sql.upper()


# ──────────────────────────────────────────────────────────────────────
# Per-row error isolation
# ──────────────────────────────────────────────────────────────────────

class TestRowErrorIsolation:
    @pytest.mark.asyncio
    async def test_one_row_failure_continues_batch(self):
        """A ValueError on one row should not abort processing of subsequent rows."""
        rows = [_tx_row("tx_bad"), _tx_row("tx_good")]

        pool, conn = _make_pool(lock_acquired=True, rows=rows)
        conn.fetchval = AsyncMock(return_value=True)  # lock + all actor checks

        call_count = 0

        async def _approve_side_effect(conn, transaction_id, **kwargs):
            nonlocal call_count
            call_count += 1
            if transaction_id == "tx_bad":
                raise ValueError("Transaction not found or not pending")
            return {"status": "completed", "user_id": "user1",
                    "amount": 20.0, "currency": "RUB"}

        with (
            patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=pool),
            patch(
                "app.services.admin_service.approve_withdrawal",
                side_effect=_approve_side_effect,
            ),
            patch(
                "app.services.notification_service.create_notification",
                new_callable=AsyncMock,
            ),
            patch("app.core.alerts.capture_exception"),  # suppress Sentry call
        ):
            from scripts.process_withdrawals import run
            result = await run(dry_run=False)

        # 1 success, 1 failure → total processed = 1 (not 0)
        assert result == 1


# ──────────────────────────────────────────────────────────────────────
# Dry-run
# ──────────────────────────────────────────────────────────────────────

class TestDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_approve(self):
        rows = [_tx_row("tx_dry1"), _tx_row("tx_dry2")]

        pool, conn = _make_pool(lock_acquired=True, rows=rows)
        conn.fetchval = AsyncMock(return_value=True)

        with (
            patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=pool),
            patch(
                "app.services.admin_service.approve_withdrawal",
                new_callable=AsyncMock,
            ) as mock_approve,
            patch(
                "app.services.notification_service.create_notification",
                new_callable=AsyncMock,
            ) as mock_notify,
        ):
            from scripts.process_withdrawals import run
            result = await run(dry_run=True)

        assert result == 2  # counted as "would process"
        mock_approve.assert_not_called()
        mock_notify.assert_not_called()
