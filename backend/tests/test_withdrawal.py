"""Tests for the withdrawal system in wallet_service and the /wallet/withdraw endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.wallet_service import (
    create_withdrawal,
    InsufficientFundsError,
    WithdrawalValidationError,
)


def _make_conn(in_transaction=True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_transaction)
    return conn


def _wallet_row(balance=1000.0, wallet_id="wallet_abc"):
    return {"id": wallet_id, "balance": balance}


# ---------------------------------------------------------------------------
# create_withdrawal — service layer
# ---------------------------------------------------------------------------


class TestCreateWithdrawal:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        """Valid withdrawal deducts balance and records pending tx."""
        from app.core import config as cfg
        monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 10.0)

        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=500.0)

        result = await create_withdrawal(conn, "user_1", 100.0, "RUB")

        assert result["amount"] == 100.0
        assert result["status"] == "pending"
        assert result["new_balance"] == 400.0
        assert result["currency"] == "RUB"
        assert "transaction_id" in result

        # UPDATE wallet + INSERT transaction = 2 execute calls
        assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_below_minimum_raises(self, monkeypatch):
        from app.core import config as cfg
        monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 10.0)

        conn = _make_conn()

        with pytest.raises(WithdrawalValidationError, match="Minimum withdrawal"):
            await create_withdrawal(conn, "user_1", 5.0, "RUB")

        # No db calls should have been made
        conn.fetchrow.assert_not_called()

    @pytest.mark.asyncio
    async def test_insufficient_funds_raises(self, monkeypatch):
        from app.core import config as cfg
        monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 10.0)

        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=50.0)

        with pytest.raises(InsufficientFundsError, match="Insufficient"):
            await create_withdrawal(conn, "user_1", 200.0, "RUB")

    @pytest.mark.asyncio
    async def test_no_wallet_raises(self, monkeypatch):
        from app.core import config as cfg
        monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 10.0)

        conn = _make_conn()
        conn.fetchrow.return_value = None

        with pytest.raises(InsufficientFundsError, match="No wallet"):
            await create_withdrawal(conn, "user_1", 50.0, "RUB")

    @pytest.mark.asyncio
    async def test_outside_transaction_raises(self, monkeypatch):
        from app.core import config as cfg
        monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 10.0)

        conn = _make_conn(in_transaction=False)

        with pytest.raises(RuntimeError, match="explicit DB transaction"):
            await create_withdrawal(conn, "user_1", 50.0, "RUB")

    @pytest.mark.asyncio
    async def test_exact_balance_withdrawal(self, monkeypatch):
        """Withdrawing exactly the full balance should leave 0."""
        from app.core import config as cfg
        monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 10.0)

        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=100.0)

        result = await create_withdrawal(conn, "user_1", 100.0, "RUB")

        assert result["new_balance"] == 0.0

    @pytest.mark.asyncio
    async def test_pending_status_in_db_insert(self, monkeypatch):
        """Verify the INSERT statement uses status='pending'."""
        from app.core import config as cfg
        monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 10.0)

        conn = _make_conn()
        conn.fetchrow.return_value = _wallet_row(balance=500.0)
        captured_sql = []

        async def capture_execute(sql, *args):
            captured_sql.append(sql)

        conn.execute = AsyncMock(side_effect=capture_execute)

        await create_withdrawal(conn, "user_1", 50.0, "RUB")

        insert_sql = [s for s in captured_sql if "INSERT INTO transactions" in s]
        assert len(insert_sql) == 1
        assert "pending" in str(conn.execute.call_args_list[-1])
