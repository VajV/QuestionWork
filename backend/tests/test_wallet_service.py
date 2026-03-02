"""Tests for wallet_service — unit tests with mocked asyncpg connection."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.wallet_service import (
    credit,
    debit,
    get_balance,
    get_all_balances,
    get_transaction_history,
    InsufficientFundsError,
    _assert_in_transaction,
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
    async def test_creates_wallet_if_missing(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None  # no wallet

        result = await get_balance(conn, "user_1", "RUB")

        assert result == 0.0
        conn.execute.assert_called_once()  # INSERT ... ON CONFLICT


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
        conn.fetchrow.return_value = None  # no wallet

        new_balance = await credit(conn, "user_1", 300.0, "RUB")

        assert new_balance == 300.0
        # INSERT wallet + INSERT transaction = 2 execute calls
        assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_credit_rejects_non_positive(self):
        conn = _make_conn()

        with pytest.raises(ValueError, match="positive"):
            await credit(conn, "user_1", 0, "RUB")

        with pytest.raises(ValueError, match="positive"):
            await credit(conn, "user_1", -10, "RUB")


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

        with pytest.raises(InsufficientFundsError, match="No wallet"):
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
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        ]

        result = await get_transaction_history(conn, "user_1", limit=10, offset=0)

        assert len(result) == 1
        assert result[0]["type"] == "income"
        assert result[0]["amount"] == 1000.0

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
