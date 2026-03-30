"""
Integration test: full withdrawal lifecycle.

flow:
  1. User calls create_withdrawal  → status='pending', balance deducted
  2. Admin calls approve_withdrawal → status='completed', audit log written
  3. Notification row created for user

All steps use mocked asyncpg connections — no live DB required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, call
from datetime import datetime, timezone

from app.services import wallet_service, admin_service, notification_service


# ──────────────────────────────────────────────────────
# Shared mock helpers
# ──────────────────────────────────────────────────────

def _make_conn(in_txn=True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_txn)
    return conn


def _wallet_row(balance=500.0, wallet_id="wallet_fl"):
    return {"id": wallet_id, "balance": balance}


# ──────────────────────────────────────────────────────
# Full lifecycle: request → admin approve → notify
# ──────────────────────────────────────────────────────

class TestWithdrawalLifecycle:
    @pytest.mark.asyncio
    async def test_full_approve_cycle(self):
        """
        Step 1: create_withdrawal deducts balance and inserts pending tx.
        Step 2: approve_withdrawal marks it completed + writes audit log.
        Step 3: create_notification is called for the user.
        """
        # ── Step 1: User requests withdrawal ──────────────────────────────
        conn_step1 = _make_conn(in_txn=True)
        conn_step1.fetchrow = AsyncMock(return_value=_wallet_row(balance=500.0))
        conn_step1.execute = AsyncMock(return_value="UPDATE 1")

        withdraw_result = await wallet_service.create_withdrawal(
            conn_step1, user_id="user_fl", amount=30.0, currency="RUB"
        )

        assert withdraw_result["status"] == "pending"
        assert withdraw_result["amount"] == 30.0
        assert withdraw_result["new_balance"] == pytest.approx(470.0)

        tx_id = withdraw_result["transaction_id"]

        # execute called twice: UPDATE wallet balance + INSERT transaction
        assert conn_step1.execute.call_count == 2

        # ── Step 2: Admin approves ──────────────────────────────────────
        tx_row = {
            "id": tx_id,
            "user_id": "user_fl",
            "type": "withdrawal",
            "amount": 30.0,
            "currency": "RUB",
            "status": "pending",
            "quest_id": None,
            "created_at": datetime.now(timezone.utc),
        }

        conn_step2 = _make_conn(in_txn=True)
        conn_step2.fetchrow = AsyncMock(return_value=tx_row)
        conn_step2.execute = AsyncMock(return_value="UPDATE 1")

        approve_result = await admin_service.approve_withdrawal(
            conn_step2, transaction_id=tx_id, admin_id="admin1", ip_address="10.0.0.1"
        )

        assert approve_result["status"] == "completed"
        assert approve_result["user_id"] == "user_fl"
        assert approve_result["amount"] == 30.0

        # execute 1: UPDATE transactions SET status = 'completed'
        # execute 2: INSERT audit log
        assert conn_step2.execute.call_count == 2

        # ── Step 3: Notification sent to user ──────────────────────────
        conn_step3 = _make_conn(in_txn=True)  # create_notification requires transaction
        conn_step3.execute = AsyncMock(return_value="INSERT 0 1")

        notif = await notification_service.create_notification(
            conn_step3,
            user_id=approve_result["user_id"],
            title="Withdrawal Approved",
            message=f"Your withdrawal of {approve_result['amount']} {approve_result['currency']} has been approved.",
            event_type="withdrawal_approved",
        )

        assert notif.user_id == "user_fl"
        assert notif.event_type == "withdrawal_approved"
        assert notif.is_read is False
        conn_step3.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_reject_cycle_refunds_balance(self):
        """
        Rejection must credit back the deducted amount.
        """
        # Create the withdrawal tx row
        tx_row = {
            "id": "tx_reject1",
            "user_id": "user_fl2",
            "type": "withdrawal",
            "amount": 40.0,
            "currency": "RUB",
            "status": "pending",
            "quest_id": None,
            "created_at": datetime.now(timezone.utc),
        }

        conn = _make_conn(in_txn=True)
        # fetchrow calls: tx row (FOR UPDATE), wallet (FOR UPDATE inside credit) → None,
        # then INSERT...RETURNING balance inside credit
        conn.fetchrow.side_effect = [tx_row, None, {"balance": 40.0}]
        conn.execute = AsyncMock(return_value="UPDATE 1")

        reject_result = await admin_service.reject_withdrawal(
            conn,
            transaction_id="tx_reject1",
            admin_id="admin1",
            reason="Identity verification failed",
        )

        assert reject_result["status"] == "rejected"
        assert reject_result["reason"] == "Identity verification failed"
        assert reject_result["amount"] == 40.0
        # new_balance is returned from credit — since wallet was None (auto-create),
        # new_balance == the refunded amount
        assert reject_result["new_balance"] == pytest.approx(40.0)

        # ── Audit log must exist ───────────────────────────────────────
        # We check that execute was called with audit INSERT somewhere
        executed_sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
        assert any("admin_logs" in sql for sql in executed_sqls)

        # ── Notification ──────────────────────────────────────────────
        conn_notif = _make_conn(in_txn=True)
        conn_notif.execute = AsyncMock(return_value="INSERT 0 1")

        notif = await notification_service.create_notification(
            conn_notif,
            user_id="user_fl2",
            title="Withdrawal Rejected",
            message=f"Your withdrawal was rejected: Identity verification failed. Amount refunded.",
            event_type="withdrawal_rejected",
        )

        assert notif.user_id == "user_fl2"
        assert notif.event_type == "withdrawal_rejected"
