"""Tests for wallet_service — unit tests with mocked asyncpg connection."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.wallet_service import (
    ALLOWED_TRANSACTION_STATUSES,
    ALLOWED_TRANSACTION_TYPES,
    credit,
    debit,
    get_balance,
    get_all_balances,
    get_total_earned,
    get_transaction_history,
    InsufficientFundsError,
    EscrowMismatchError,
    _assert_in_transaction,
    quantize_money,
    split_payment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn(in_transaction=True):
    """Create a mock asyncpg connection with async methods."""
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_transaction)
    return conn


def _wallet_row(balance=1000.0, wallet_id="wallet_abc123", version=1):
    """Fake asyncpg Record-like dict for a wallet row."""
    return {
        "id": wallet_id,
        "balance": balance,
        "version": version,
        "currency": "RUB",
        "updated_at": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# get_balance
# ---------------------------------------------------------------------------


class TestGetBalance:
    @pytest.mark.asyncio
    async def test_returns_existing_balance(self):
        conn = _make_conn()
        conn.fetchrow.return_value = {"balance": 500.0}

        result = await get_balance(conn, "user_1", "RUB")

        assert result == 500.0
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_if_wallet_missing(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None  # no wallet

        result = await get_balance(conn, "user_1", "RUB")

        assert result == 0.0
        conn.execute.assert_not_called()


# ---------------------------------------------------------------------------
# get_all_balances
# ---------------------------------------------------------------------------


class TestGetAllBalances:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        conn = _make_conn()
        conn.fetch.return_value = [
            {"currency": "RUB", "balance": 100.0, "version": 1, "updated_at": None},
            {"currency": "USD", "balance": 50.0, "version": 2, "updated_at": None},
        ]

        result = await get_all_balances(conn, "user_1")

        assert len(result) == 2
        assert result[0]["currency"] == "RUB"
        assert result[1]["balance"] == 50.0

    @pytest.mark.asyncio
    async def test_empty_wallets(self):
        conn = _make_conn()
        conn.fetch.return_value = []

        result = await get_all_balances(conn, "user_1")
        assert result == []


# ---------------------------------------------------------------------------
# credit
# ---------------------------------------------------------------------------


class TestCredit:
    @pytest.mark.asyncio
    async def test_credit_existing_wallet(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=500.0)

        new_balance = await credit(conn, "user_1", 200.0, "RUB", quest_id="q1")

        assert new_balance == 700.0
        # UPDATE wallet + INSERT transaction = 2 execute calls
        assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_credit_creates_wallet_if_missing(self):
        conn = _make_conn()
        # First fetchrow: SELECT FOR UPDATE → None (no wallet)
        # Second fetchrow: INSERT...ON CONFLICT...RETURNING → balance
        conn.fetchrow.side_effect = [None, {"balance": 300.0}]

        new_balance = await credit(conn, "user_1", 300.0, "RUB")

        assert new_balance == 300.0
        # Only INSERT transaction via execute (wallet INSERT is now fetchrow with RETURNING)
        assert conn.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_credit_rejects_non_positive(self):
        conn = _make_conn()

        with pytest.raises(ValueError, match="positive"):
            await credit(conn, "user_1", 0, "RUB")

        with pytest.raises(ValueError, match="positive"):
            await credit(conn, "user_1", -10, "RUB")

    @pytest.mark.asyncio
    async def test_credit_rejects_unsupported_transaction_type(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=500.0)

        with pytest.raises(ValueError, match="Unsupported transaction type"):
            await credit(conn, "user_1", 50.0, "RUB", tx_type="bad_type")

    @pytest.mark.asyncio
    async def test_credit_quantizes_amount_and_balance(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=500.005)

        new_balance = await credit(conn, "user_1", 200.005, "RUB")

        assert new_balance == quantize_money("700.02")
        wallet_update_args = conn.execute.call_args_list[0][0]
        tx_insert_args = conn.execute.call_args_list[1][0]
        assert wallet_update_args[1] == quantize_money("700.02")
        assert tx_insert_args[4] == quantize_money("200.01")


# ---------------------------------------------------------------------------
# debit
# ---------------------------------------------------------------------------


class TestDebit:
    @pytest.mark.asyncio
    async def test_debit_sufficient_funds(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=1000.0)

        new_balance = await debit(conn, "user_1", 300.0, "RUB", quest_id="q1")

        assert new_balance == 700.0
        assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_debit_insufficient_funds(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=100.0)

        with pytest.raises(InsufficientFundsError, match="Insufficient"):
            await debit(conn, "user_1", 500.0, "RUB")

    @pytest.mark.asyncio
    async def test_debit_no_wallet(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None

        with pytest.raises(InsufficientFundsError, match="Insufficient funds"):
            await debit(conn, "user_1", 100.0, "RUB")

    @pytest.mark.asyncio
    async def test_debit_rejects_non_positive(self):
        conn = _make_conn()

        with pytest.raises(ValueError, match="positive"):
            await debit(conn, "user_1", 0, "RUB")

    @pytest.mark.asyncio
    async def test_debit_exact_balance(self):
        """Debiting the exact balance should succeed (balance → 0)."""
        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=500.0)

        new_balance = await debit(conn, "user_1", 500.0, "RUB")
        assert new_balance == 0.0

    @pytest.mark.asyncio
    async def test_debit_quantizes_amount_and_balance(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=1000.005)

        new_balance = await debit(conn, "user_1", 300.005, "RUB")

        assert new_balance == quantize_money("700.00")
        wallet_update_args = conn.execute.call_args_list[0][0]
        tx_insert_args = conn.execute.call_args_list[1][0]
        assert wallet_update_args[1] == quantize_money("700.00")
        assert tx_insert_args[4] == quantize_money("300.01")


class TestMoneyNormalization:
    def test_quantize_money_rounds_half_up(self):
        assert quantize_money("10") == quantize_money("10.00")
        assert quantize_money("10.004") == quantize_money("10.00")
        assert quantize_money("10.005") == quantize_money("10.01")

    def test_allowed_transaction_sets_match_batch1_constraints(self):
        assert ALLOWED_TRANSACTION_TYPES == {
            "income",
            "expense",
            "hold",
            "refund",
            "urgent_bonus_charge",
            "urgent_bonus",
            "commission",
            "withdrawal",
            "admin_adjust",
            "credit",
            "quest_payment",
            "release",
            "platform_fee",
        }
        assert ALLOWED_TRANSACTION_STATUSES == {
            "pending",
            "completed",
            "rejected",
            "refunded",
            "held",
            "failed",
        }


class TestSplitPayment:
    @pytest.mark.asyncio
    async def test_rejects_hold_amount_mismatch(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            {"id": "hold_1", "amount": 1000.0},
        ]

        with pytest.raises(EscrowMismatchError, match="Escrow hold amount does not match payout amount"):
            await split_payment(
                conn,
                client_id="client_1",
                freelancer_id="fl_1",
                gross_amount=1500.0,
                currency="RUB",
                quest_id="quest_1",
                fee_percent=10,
            )


# ---------------------------------------------------------------------------
# get_transaction_history
# ---------------------------------------------------------------------------


class TestTransactionHistory:
    @pytest.mark.asyncio
    async def test_returns_transactions(self):
        conn = _make_conn()
        conn.fetch.return_value = [
            {
                "id": "tx_1",
                "quest_id": "q1",
                "amount": 1000.0,
                "currency": "RUB",
                "type": "income",
                "status": "completed",
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        ]

        result = await get_transaction_history(conn, "user_1", limit=10, offset=0)

        assert len(result) == 1
        assert result[0]["type"] == "income"
        assert result[0]["amount"] == 1000.0
        assert result[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_empty_history(self):
        conn = _make_conn()
        conn.fetch.return_value = []

        result = await get_transaction_history(conn, "user_1")
        assert result == []


# ---------------------------------------------------------------------------
# Transaction context guard
# ---------------------------------------------------------------------------


class TestTransactionGuard:
    @pytest.mark.asyncio
    async def test_credit_outside_transaction_raises(self):
        conn = _make_conn(in_transaction=False)
        with pytest.raises(RuntimeError, match="explicit DB transaction"):
            await credit(conn, "user_1", 100.0, "RUB")

    @pytest.mark.asyncio
    async def test_debit_outside_transaction_raises(self):
        conn = _make_conn(in_transaction=False)
        with pytest.raises(RuntimeError, match="explicit DB transaction"):
            await debit(conn, "user_1", 100.0, "RUB")

    def test_assert_in_transaction_ok(self):
        conn = MagicMock()
        conn.is_in_transaction.return_value = True
        _assert_in_transaction(conn)  # should not raise

    def test_assert_in_transaction_raises(self):
        conn = MagicMock()
        conn.is_in_transaction.return_value = False
        with pytest.raises(RuntimeError, match="explicit DB transaction"):
            _assert_in_transaction(conn)


# ---------------------------------------------------------------------------
# P0-2: get_total_earned uses correct transaction types
# ---------------------------------------------------------------------------


class TestGetTotalEarned:
    @pytest.mark.asyncio
    async def test_total_earned_after_quest_completion(self):
        """get_total_earned sums 'income' and 'commission' with status='completed'."""
        conn = _make_conn()
        conn.fetchrow.return_value = {"total": 1500.0}

        result = await get_total_earned(conn, "user_1")

        assert result == 1500.0
        # Verify the SQL uses correct types
        call_args = conn.fetchrow.call_args
        sql = call_args[0][0]
        assert "'income'" in sql
        assert "'commission'" in sql
        assert "status = 'completed'" in sql
        # Old wrong types must NOT appear
        assert "'credit'" not in sql
        assert "'quest_payment'" not in sql

    @pytest.mark.asyncio
    async def test_total_earned_zero_when_no_transactions(self):
        conn = _make_conn()
        conn.fetchrow.return_value = {"total": 0}

        result = await get_total_earned(conn, "user_1")
        assert result == 0


# ---------------------------------------------------------------------------
# P0-3: concurrent first-credit race condition
# ---------------------------------------------------------------------------


class TestConcurrentCredit:
    @pytest.mark.asyncio
    async def test_concurrent_first_credit_no_race(self):
        """When wallet doesn't exist, credit uses INSERT...ON CONFLICT
        so concurrent calls don't crash with UniqueViolationError."""
        conn = _make_conn()
        # SELECT FOR UPDATE returns None, INSERT ON CONFLICT RETURNING returns balance
        conn.fetchrow.side_effect = [None, {"balance": 500.0}]

        result = await credit(conn, "user_1", 500.0, "RUB")

        assert result == 500.0
        # Verify the INSERT uses ON CONFLICT
        insert_call = conn.fetchrow.call_args_list[1]
        sql = insert_call[0][0]
        assert "ON CONFLICT" in sql
        assert "user_id, currency" in sql
