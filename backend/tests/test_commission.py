"""Tests for the commission split_payment function in wallet_service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.wallet_service import (
    split_payment,
    InsufficientFundsError,
)


def _wallet_row(balance=10000.0, wallet_id="wallet_test"):
    return {"id": wallet_id, "balance": balance}


def _make_conn():
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=True)
    return conn


# ---------------------------------------------------------------------------
# split_payment math
# ---------------------------------------------------------------------------


class TestSplitPayment:
    @pytest.mark.asyncio
    async def test_10_percent_fee(self):
        """Freelancer gets 90%, platform gets 10% on a 100 RUB quest."""
        conn = _make_conn()
        # fetchrow calls: freelancer wallet, platform wallet
        conn.fetchrow.side_effect = [
            _wallet_row(0.0, "wallet_fl"),   # freelancer wallet (no existing → INSERT path)
            _wallet_row(0.0, "wallet_plat"), # platform wallet
        ]
        conn.fetchrow.side_effect = [None, None]  # auto-create paths for both

        result = await split_payment(
            conn,
            client_id="user_client",
            freelancer_id="user_freelancer",
            gross_amount=100.0,
            currency="RUB",
            quest_id="q1",
            fee_percent=10.0,
        )

        assert result["freelancer_amount"] == 90.0
        assert result["platform_fee"] == 10.0
        assert result["gross_amount"] == 100.0
        assert result["fee_percent"] == 10.0

    @pytest.mark.asyncio
    async def test_zero_fee(self):
        """0% fee → freelancer gets 100%, no platform credit call."""
        conn = _make_conn()
        conn.fetchrow.side_effect = [None]  # only freelancer wallet needed

        result = await split_payment(
            conn,
            client_id="c",
            freelancer_id="f",
            gross_amount=500.0,
            fee_percent=0.0,
        )
        assert result["freelancer_amount"] == 500.0
        assert result["platform_fee"] == 0.0
        assert result["platform_balance"] is None  # no credit call made

    @pytest.mark.asyncio
    async def test_uses_settings_fee_by_default(self, monkeypatch):
        """When fee_percent is omitted, uses settings.PLATFORM_FEE_PERCENT."""
        from app.core import config as cfg_mod
        monkeypatch.setattr(cfg_mod.settings, "PLATFORM_FEE_PERCENT", 15.0)

        conn = _make_conn()
        conn.fetchrow.side_effect = [None, None]

        result = await split_payment(
            conn,
            client_id="c",
            freelancer_id="f",
            gross_amount=200.0,
        )
        assert result["fee_percent"] == 15.0
        assert result["platform_fee"] == 30.0
        assert result["freelancer_amount"] == 170.0

    @pytest.mark.asyncio
    async def test_fee_100_percent_raises(self):
        conn = _make_conn()
        with pytest.raises(ValueError, match="fee_percent"):
            await split_payment(
                conn,
                client_id="c",
                freelancer_id="f",
                gross_amount=100.0,
                fee_percent=100.0,
            )

    @pytest.mark.asyncio
    async def test_negative_fee_raises(self):
        conn = _make_conn()
        with pytest.raises(ValueError, match="fee_percent"):
            await split_payment(
                conn,
                client_id="c",
                freelancer_id="f",
                gross_amount=100.0,
                fee_percent=-5.0,
            )

    @pytest.mark.asyncio
    async def test_outside_transaction_raises(self):
        conn = _make_conn()
        conn.is_in_transaction = MagicMock(return_value=False)
        with pytest.raises(RuntimeError, match="explicit DB transaction"):
            await split_payment(
                conn,
                client_id="c",
                freelancer_id="f",
                gross_amount=100.0,
            )

    @pytest.mark.asyncio
    async def test_rounding_two_decimal_places(self):
        """1/3 fee on 100: platform_fee + freelancer_amount == gross_amount."""
        conn = _make_conn()
        conn.fetchrow.side_effect = [None, None]

        result = await split_payment(
            conn,
            client_id="c",
            freelancer_id="f",
            gross_amount=100.0,
            fee_percent=33.333,
        )
        total = round(result["freelancer_amount"] + result["platform_fee"], 2)
        assert abs(total - 100.0) <= 0.01  # within 1 kopek

    @pytest.mark.asyncio
    async def test_ledger_balance_conservation_100_transactions(self, monkeypatch):
        """After 100 transactions of $100 each at 10%:
        - platform should have received $1000 total
        - Each call should yield platform_fee=10.0
        """
        conn = _make_conn()
        conn.fetchrow.side_effect = [None, None] * 100  # 200 fetchrow calls

        platform_total = 0.0
        freelancer_total = 0.0

        for _ in range(100):
            r = await split_payment(
                conn,
                client_id="c",
                freelancer_id="f",
                gross_amount=100.0,
                fee_percent=10.0,
            )
            platform_total += r["platform_fee"]
            freelancer_total += r["freelancer_amount"]

        assert abs(platform_total - 1000.0) < 0.01
        assert abs(freelancer_total - 9000.0) < 0.01
        assert abs(platform_total + freelancer_total - 10000.0) < 0.01
