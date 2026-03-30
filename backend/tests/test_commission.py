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
        conn.fetchrow.side_effect = [
            None,                                    # split_payment: hold_tx check (no escrow)
            _wallet_row(10000.0, "wallet_client"),  # debit: client wallet
            None, {"balance": 90.0},                 # credit: freelancer wallet INSERT
            None, {"balance": 10.0},                 # credit: platform wallet INSERT
        ]

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
        conn.fetchrow.side_effect = [
            None,                                    # split_payment: hold_tx check (no escrow)
            _wallet_row(10000.0, "wallet_client"),  # debit: client wallet
            None, {"balance": 500.0},                # credit: freelancer wallet INSERT
        ]

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
        conn.fetchrow.side_effect = [
            None,                                    # split_payment: hold_tx check (no escrow)
            _wallet_row(10000.0, "wallet_client"),  # debit: client wallet
            None, {"balance": 170.0},                # credit: freelancer wallet INSERT
            None, {"balance": 30.0},                 # credit: platform wallet INSERT
        ]

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
        """1/3-ish fee on 100: platform_fee + freelancer_amount == gross_amount."""
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            None,                                    # split_payment: hold_tx check (no escrow)
            _wallet_row(10000.0, "wallet_client"),  # debit: client wallet
            None, {"balance": 73.33},                # credit: freelancer wallet INSERT
            None, {"balance": 26.67},                # credit: platform wallet INSERT
        ]

        result = await split_payment(
            conn,
            client_id="c",
            freelancer_id="f",
            gross_amount=100.0,
            fee_percent=26.667,
        )
        total = float(result["freelancer_amount"]) + float(result["platform_fee"])
        assert abs(total - 100.0) <= 0.01  # within 1 kopek

    @pytest.mark.asyncio
    async def test_ledger_balance_conservation_100_transactions(self, monkeypatch):
        """After 100 transactions of $100 each at 10%:
        - platform should have received $1000 total
        - Each call should yield platform_fee=10.0
        """
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            None,                                    # split_payment: hold_tx check (no escrow)
            _wallet_row(10000.0, "wallet_client"),  # debit: client wallet
            None, {"balance": 90.0},                 # credit: freelancer wallet INSERT
            None, {"balance": 10.0},                 # credit: platform wallet INSERT
        ] * 100

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
            platform_total += float(r["platform_fee"])
            freelancer_total += float(r["freelancer_amount"])

        assert abs(platform_total - 1000.0) < 0.01
        assert abs(freelancer_total - 9000.0) < 0.01
        assert abs(platform_total + freelancer_total - 10000.0) < 0.01

    @pytest.mark.asyncio
    async def test_existing_hold_is_released_before_direct_debit(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            {"id": "hold_1", "amount": 100.0},
            {"balance": 0.0},
        ]

        with patch("app.services.wallet_service.release_hold", new=AsyncMock(return_value=100.0)) as mock_release_hold, \
             patch("app.services.wallet_service.debit", new=AsyncMock()) as mock_debit, \
             patch("app.services.wallet_service.credit", new=AsyncMock(side_effect=[90.0, 10.0])) as mock_credit:
            result = await split_payment(
                conn,
                client_id="client_1",
                freelancer_id="freelancer_1",
                gross_amount=100.0,
                currency="RUB",
                quest_id="quest_1",
                fee_percent=10.0,
            )

        assert result["client_balance"] == 0.0
        assert result["freelancer_amount"] == 90.0
        assert result["platform_fee"] == 10.0
        mock_release_hold.assert_awaited_once_with(conn, "client_1", "quest_1", "RUB")
        mock_debit.assert_not_awaited()
        assert mock_credit.await_count == 2

    @pytest.mark.asyncio
    async def test_no_hold_with_insufficient_balance_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None

        with patch("app.services.wallet_service.debit", new=AsyncMock(side_effect=InsufficientFundsError("Insufficient funds"))):
            with pytest.raises(InsufficientFundsError, match="Insufficient funds"):
                await split_payment(
                    conn,
                    client_id="client_1",
                    freelancer_id="freelancer_1",
                    gross_amount=100.0,
                    currency="RUB",
                    quest_id="quest_1",
                    fee_percent=10.0,
                )

    @pytest.mark.asyncio
    async def test_client_surcharge_paid_above_budget(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            {"id": "hold_1", "amount": 100.0},
            {"balance": 50.0},
        ]

        with patch("app.services.wallet_service.release_hold", new=AsyncMock(return_value=100.0)) as mock_release_hold, \
             patch("app.services.wallet_service.debit", new=AsyncMock(return_value=40.0)) as mock_debit, \
             patch("app.services.wallet_service.credit", new=AsyncMock(side_effect=[90.0, 100.0, 10.0])) as mock_credit:
            result = await split_payment(
                conn,
                client_id="client_1",
                freelancer_id="freelancer_1",
                gross_amount=100.0,
                currency="RUB",
                quest_id="quest_1",
                fee_percent=10.0,
                client_surcharge_amount=10.0,
            )

        mock_release_hold.assert_awaited_once_with(conn, "client_1", "quest_1", "RUB")
        mock_debit.assert_awaited_once()
        assert mock_credit.await_count == 3
        assert result["base_freelancer_amount"] == 90.0
        assert result["client_surcharge_amount"] == 10.0
        assert result["freelancer_amount"] == 100.0
        assert result["total_client_charge"] == 110.0
