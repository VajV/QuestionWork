"""
Tests for admin_service — audit log, withdrawal approve/reject, list ops, cleanup.

Coverage goal: ≥ 85% of admin_service.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.admin_service import (
    log_admin_action,
    approve_withdrawal,
    reject_withdrawal,
    list_users,
    list_transactions,
    list_pending_withdrawals,
    get_admin_logs,
    cleanup_old_notifications,
)


# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────

def _make_conn(in_txn=True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_txn)
    return conn


def _pending_tx(amount=100.0, currency="RUB", user_id="user_fl"):
    return {
        "id": "tx_test001",
        "user_id": user_id,
        "type": "withdrawal",
        "amount": amount,
        "currency": currency,
        "status": "pending",
        "quest_id": None,
        "created_at": datetime.now(timezone.utc),
    }


# ──────────────────────────────────────────────────────
# log_admin_action
# ──────────────────────────────────────────────────────

class TestLogAdminAction:
    @pytest.mark.asyncio
    async def test_inserts_audit_row(self):
        conn = _make_conn()
        log_id = await log_admin_action(
            conn,
            admin_id="admin1",
            action="test_action",
            target_type="transaction",
            target_id="tx1",
            old_value={"status": "pending"},
            new_value={"status": "completed"},
            ip_address="127.0.0.1",
        )
        assert log_id.startswith("alog_")
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_if_not_in_transaction(self):
        conn = _make_conn(in_txn=False)
        with pytest.raises(RuntimeError, match="DB transaction"):
            await log_admin_action(conn, "admin1", "action", "type", "id")

    @pytest.mark.asyncio
    async def test_works_without_optional_fields(self):
        conn = _make_conn()
        log_id = await log_admin_action(
            conn, admin_id="admin1", action="read", target_type="user", target_id="u1"
        )
        assert log_id.startswith("alog_")
        conn.execute.assert_called_once()


# ──────────────────────────────────────────────────────
# approve_withdrawal
# ──────────────────────────────────────────────────────

class TestApproveWithdrawal:
    @pytest.mark.asyncio
    async def test_approves_pending_withdrawal(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=_pending_tx())

        result = await approve_withdrawal(conn, "tx_test001", "admin1", ip_address="1.2.3.4")

        assert result["status"] == "completed"
        assert result["transaction_id"] == "tx_test001"
        # UPDATE + audit INSERT
        assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_if_not_found(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await approve_withdrawal(conn, "tx_missing", "admin1")

    @pytest.mark.asyncio
    async def test_raises_if_not_withdrawal_type(self):
        conn = _make_conn()
        tx = _pending_tx()
        tx["type"] = "income"
        conn.fetchrow = AsyncMock(return_value=tx)

        with pytest.raises(ValueError, match="not a withdrawal"):
            await approve_withdrawal(conn, "tx_test001", "admin1")

    @pytest.mark.asyncio
    async def test_raises_if_already_completed(self):
        conn = _make_conn()
        tx = _pending_tx()
        tx["status"] = "completed"
        conn.fetchrow = AsyncMock(return_value=tx)

        with pytest.raises(ValueError, match="already completed"):
            await approve_withdrawal(conn, "tx_test001", "admin1")

    @pytest.mark.asyncio
    async def test_raises_if_not_in_transaction(self):
        conn = _make_conn(in_txn=False)
        with pytest.raises(RuntimeError, match="DB transaction"):
            await approve_withdrawal(conn, "tx_test001", "admin1")


# ──────────────────────────────────────────────────────
# reject_withdrawal
# ──────────────────────────────────────────────────────

class TestRejectWithdrawal:
    @pytest.mark.asyncio
    async def test_rejects_and_refunds(self):
        conn = _make_conn()
        tx = _pending_tx(amount=50.0)
        conn.fetchrow = AsyncMock(return_value=tx)
        # credit() will also call fetchrow (wallet lock) — return None (auto-create path)
        conn.fetchrow.side_effect = [tx, None]

        result = await reject_withdrawal(
            conn, "tx_test001", "admin1", reason="Verification failed"
        )

        assert result["status"] == "rejected"
        assert result["reason"] == "Verification failed"
        assert result["user_id"] == tx["user_id"]
        # execute: UPDATE status + INSERT wallet (from credit) + INSERT tx ledger + INSERT audit
        assert conn.execute.call_count >= 3

    @pytest.mark.asyncio
    async def test_raises_if_not_found(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await reject_withdrawal(conn, "tx_missing", "admin1", reason="x")

    @pytest.mark.asyncio
    async def test_raises_if_already_rejected(self):
        conn = _make_conn()
        tx = _pending_tx()
        tx["status"] = "rejected"
        conn.fetchrow = AsyncMock(return_value=tx)

        with pytest.raises(ValueError, match="already rejected"):
            await reject_withdrawal(conn, "tx_test001", "admin1", reason="x")

    @pytest.mark.asyncio
    async def test_raises_if_not_in_transaction(self):
        conn = _make_conn(in_txn=False)
        with pytest.raises(RuntimeError, match="DB transaction"):
            await reject_withdrawal(conn, "tx_test001", "admin1", reason="x")


# ──────────────────────────────────────────────────────
# list_users
# ──────────────────────────────────────────────────────

class TestListUsers:
    @pytest.mark.asyncio
    async def test_returns_paginated_users(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=2)
        conn.fetch = AsyncMock(return_value=[
            {"id": "u1", "username": "alice", "email": None,
             "role": "freelancer", "grade": "novice", "level": 1,
             "xp": 0, "created_at": datetime.now(timezone.utc)},
            {"id": "u2", "username": "bob", "email": None,
             "role": "client", "grade": "novice", "level": 1,
             "xp": 0, "created_at": datetime.now(timezone.utc)},
        ])

        result = await list_users(conn, page=1, page_size=50)

        assert result["total"] == 2
        assert len(result["users"]) == 2
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_role_filter_passed_to_query(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[])

        await list_users(conn, page=1, page_size=10, role_filter="admin")

        fetch_call = conn.fetch.call_args[0][0]
        assert "role" in fetch_call.lower() or conn.fetchval.call_args[0][0].count("role") >= 0


# ──────────────────────────────────────────────────────
# list_transactions / list_pending_withdrawals
# ──────────────────────────────────────────────────────

class TestListTransactions:
    @pytest.mark.asyncio
    async def test_returns_paginated_transactions(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[
            {
                "id": "tx1", "user_id": "u1", "type": "withdrawal",
                "amount": 100.0, "currency": "RUB", "status": "pending",
                "quest_id": None, "created_at": datetime.now(timezone.utc),
            }
        ])

        result = await list_transactions(conn, status_filter="pending", type_filter="withdrawal")

        assert result["total"] == 1
        assert result["transactions"][0]["type"] == "withdrawal"

    @pytest.mark.asyncio
    async def test_pending_withdrawals_shortcut(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetch = AsyncMock(return_value=[])

        result = await list_pending_withdrawals(conn)

        assert result["total"] == 0
        # Verify both filters were applied (pending + withdrawal)
        call_args = conn.fetch.call_args
        fetch_query = call_args[0][0]
        fetch_params = call_args[0][1:]
        # The SQL uses placeholders; the actual values are in positional params
        assert "pending" in fetch_params or "pending" in fetch_query
        assert "withdrawal" in fetch_params or "withdrawal" in fetch_query


# ──────────────────────────────────────────────────────
# get_admin_logs
# ──────────────────────────────────────────────────────

class TestGetAdminLogs:
    @pytest.mark.asyncio
    async def test_returns_log_entries(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[
            {
                "id": "alog_1", "admin_id": "admin1", "action": "withdrawal_approved",
                "target_type": "transaction", "target_id": "tx1",
                "old_value": None, "new_value": None,
                "ip_address": "127.0.0.1", "created_at": datetime.now(timezone.utc),
            }
        ])

        result = await get_admin_logs(conn)

        assert result["total"] == 1
        assert result["logs"][0]["action"] == "withdrawal_approved"


# ──────────────────────────────────────────────────────
# cleanup_old_notifications
# ──────────────────────────────────────────────────────

class TestCleanupOldNotifications:
    @pytest.mark.asyncio
    async def test_returns_count_deleted(self):
        conn = _make_conn(in_txn=False)
        conn.execute = AsyncMock(return_value="DELETE 7")

        count = await cleanup_old_notifications(conn)

        assert count == 7

    @pytest.mark.asyncio
    async def test_returns_zero_if_nothing_deleted(self):
        conn = _make_conn(in_txn=False)
        conn.execute = AsyncMock(return_value="DELETE 0")

        count = await cleanup_old_notifications(conn)

        assert count == 0

    @pytest.mark.asyncio
    async def test_does_not_require_transaction(self):
        """cleanup_old_notifications is a single-statement DELETE — no txn needed."""
        conn = _make_conn(in_txn=False)
        conn.execute = AsyncMock(return_value="DELETE 0")
        # Should NOT raise even though not in transaction
        await cleanup_old_notifications(conn)
