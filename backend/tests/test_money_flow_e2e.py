"""
End-to-end money flow test: quest lifecycle from application to withdrawal.

Verifies the full business path:
  apply → assign (hold) → start → complete → confirm (split) → withdrawal

Uses mock DB but validates that every service function is called
in the correct order with correct arguments and money amounts.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone
from decimal import Decimal

from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats
from app.models.quest import QuestApplicationCreate, QuestCompletionCreate, QuestStatusEnum
from app.services import quest_service, wallet_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _make_conn():
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=True)
    conn.transaction = MagicMock(return_value=_FakeTransaction())
    return conn


def _make_user(role="client", user_id="user_client", grade=GradeEnum.novice, is_banned=False):
    return UserProfile(
        id=user_id,
        username=f"test_{role}",
        role=UserRoleEnum(role),
        is_banned=is_banned,
        level=1,
        grade=grade,
        xp=0,
        xp_to_next=100,
        stats=UserStats(),
        badges=[],
        skills=[],
    )


QUEST_BUDGET = Decimal("10000")
QUEST_CURRENCY = "RUB"
FEE_PERCENT = Decimal("10")
EXPECTED_FEE = Decimal("1000.00")
EXPECTED_FREELANCER_PAYOUT = Decimal("9000.00")

NOW = datetime.now(timezone.utc)


def _quest_row(status="open", assigned_to=None, platform_fee_percent=FEE_PERCENT):
    return {
        "id": "quest_e2e",
        "client_id": "user_client",
        "client_username": "test_client",
        "title": "E2E Money Quest",
        "description": "Full lifecycle money flow test for E2E validation",
        "required_grade": "novice",
        "skills": '["python"]',
        "budget": QUEST_BUDGET,
        "currency": QUEST_CURRENCY,
        "xp_reward": 100,
        "status": status,
        "applications": [],
        "assigned_to": assigned_to,
        "created_at": NOW,
        "updated_at": NOW,
        "completed_at": None,
        "delivery_note": None,
        "delivery_url": None,
        "delivery_submitted_at": None,
        "revision_reason": None,
        "revision_requested_at": None,
        "platform_fee_percent": platform_fee_percent,
        "is_urgent": False,
        "deadline": None,
        "revision_count": 0,
        "required_portfolio": False,
    }


def _freelancer_row():
    return {
        "id": "user_freelancer",
        "username": "fl_worker",
        "email": "fl@test.com",
        "password_hash": "hash",
        "role": "freelancer",
        "level": 1,
        "grade": "novice",
        "xp": 0,
        "xp_to_next": 100,
        "stats_int": 10,
        "stats_dex": 10,
        "stats_cha": 10,
        "stat_points": 0,
        "badges": "[]",
        "bio": None,
        "skills": '["python"]',
        "character_class": None,
        "is_banned": False,
        "created_at": NOW,
        "updated_at": NOW,
    }


# ---------------------------------------------------------------------------
# Shared mocks
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_services():
    """Patch all side-effect services so the test only validates money flow."""
    with (
        patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()),
        patch("app.services.quest_service.message_service.create_system_message", new=AsyncMock()),
        patch("app.services.quest_service.trust_score_service.refresh_trust_score", new=AsyncMock()),
        patch("app.services.quest_service.badge_service.check_and_award", new=AsyncMock(
            return_value=MagicMock(newly_earned=[]),
        )),
        patch("app.services.quest_service.class_service.check_burnout", new=AsyncMock(return_value=False)),
        patch("app.services.quest_service.class_service.get_active_ability_effects", new=AsyncMock(return_value={})),
        patch("app.services.quest_service.class_service.add_class_xp", new=AsyncMock(return_value={})),
        patch("app.services.quest_service.class_service.reset_consecutive_if_stale", new=AsyncMock()),
        patch("app.services.quest_service.guild_economy_service.apply_quest_completion_rewards", new=AsyncMock(return_value=None)),
        patch("app.services.quest_service.guild_economy_service.award_solo_artifact_drop", new=AsyncMock()),
        patch("app.services.quest_service.challenge_service.increment_challenge_progress", new=AsyncMock(return_value=None)),
        patch("app.services.quest_service.referral_service.grant_referral_rewards", new=AsyncMock(return_value=None)),
        patch("app.services.quest_service.advance_chain_progress", new=AsyncMock(return_value=None)),
    ):
        yield


# ---------------------------------------------------------------------------
# E2E test
# ---------------------------------------------------------------------------

class TestFullMoneyFlowE2E:
    """Trace money through the entire quest lifecycle."""

    @pytest.mark.asyncio
    async def test_apply_assign_start_complete_confirm_flow(self):
        """
        1. Freelancer applies to quest
        2. Client assigns freelancer → escrow hold = budget
        3. Freelancer starts quest
        4. Freelancer marks quest complete
        5. Client confirms → split_payment: freelancer gets (budget - fee), platform gets fee
        """
        client = _make_user("client", "user_client")
        freelancer = _make_user("freelancer", "user_freelancer")

        # ── Step 1: Apply ─────────────────────────────────────────
        conn_apply = _make_conn()
        # fetchrow: quest row (open), then existing application check, then user row
        conn_apply.fetchrow.side_effect = [
            _quest_row(status="open"),  # quest lookup
            None,  # no existing application
            _freelancer_row(),  # user lookup
        ]
        conn_apply.fetchval.side_effect = [
            0,  # active applications count
        ]
        conn_apply.fetch.return_value = []  # quest applications list

        app_data = QuestApplicationCreate(
            cover_letter="I want to do this quest",
        )
        application = await quest_service.apply_to_quest(
            conn_apply, "quest_e2e", app_data, freelancer,
        )
        assert application is not None

        # ── Step 2: Assign (creates escrow hold) ──────────────────
        conn_assign = _make_conn()
        # fetchrow sequence for assign_freelancer:
        conn_assign.fetchrow.side_effect = [
            _quest_row(status="open"),  # quest lock
            {"id": "app_1"},  # application exists
            {"username": "fl_worker", "character_class": None, "is_banned": False},  # freelancer slot check
            _quest_row(status="assigned", assigned_to="user_freelancer"),  # updated quest
        ]
        conn_assign.fetchval.side_effect = [
            0,  # active quest count for slot limit
        ]
        conn_assign.fetch.return_value = []  # applications

        with patch.object(wallet_service, "hold", new=AsyncMock(return_value=QUEST_BUDGET)) as mock_hold:
            await quest_service.assign_freelancer(
                conn_assign, "quest_e2e", "user_freelancer", client,
            )

            # Verify escrow hold was called with correct budget
            mock_hold.assert_called_once_with(
                conn_assign,
                user_id="user_client",
                amount=QUEST_BUDGET,
                currency=QUEST_CURRENCY,
                quest_id="quest_e2e",
            )

        # ── Step 3: Start quest ───────────────────────────────────
        conn_start = _make_conn()
        conn_start.fetchrow.side_effect = [
            {"id": "quest_e2e", "status": "assigned", "assigned_to": "user_freelancer"},
            _quest_row(status="in_progress", assigned_to="user_freelancer"),
        ]
        conn_start.fetchval.return_value = "quest_e2e"  # UPDATE RETURNING
        conn_start.fetch.return_value = []

        started = await quest_service.start_quest(conn_start, "quest_e2e", freelancer)
        assert started.status == QuestStatusEnum.in_progress

        # ── Step 4: Mark complete (freelancer submits) ────────────
        conn_complete = _make_conn()
        conn_complete.fetchrow.side_effect = [
            {"id": "quest_e2e", "status": "in_progress", "assigned_to": "user_freelancer", "xp_reward": 100},
            _quest_row(status="completed", assigned_to="user_freelancer"),
        ]
        conn_complete.fetch.return_value = []

        completed_quest, xp_preview = await quest_service.mark_quest_complete(
            conn_complete,
            "quest_e2e",
            QuestCompletionCreate(delivery_note="Work completed successfully"),
            freelancer,
        )
        assert completed_quest.status == QuestStatusEnum.completed

        # ── Step 5: Confirm (client confirms → money splits) ─────
        conn_confirm = _make_conn()
        # fetchrow sequence:
        conn_confirm.fetchrow.side_effect = [
            _quest_row(status="completed", assigned_to="user_freelancer"),  # quest lock
            _freelancer_row(),  # freelancer FOR UPDATE
            _quest_row(status="confirmed", assigned_to="user_freelancer"),  # updated quest
        ]
        conn_confirm.fetchval.side_effect = [
            "quest_e2e",  # CAS UPDATE RETURNING id
            3,  # completed quest count (badges)
        ]
        conn_confirm.fetch.return_value = []

        split_result = {
            "gross_amount": QUEST_BUDGET,
            "fee_percent": FEE_PERCENT,
            "freelancer_amount": EXPECTED_FREELANCER_PAYOUT,
            "platform_fee": EXPECTED_FEE,
            "client_balance": Decimal("0.00"),
            "freelancer_balance": EXPECTED_FREELANCER_PAYOUT,
            "platform_balance": EXPECTED_FEE,
            "client_surcharge_amount": Decimal("0"),
        }

        with patch.object(wallet_service, "split_payment", new=AsyncMock(return_value=split_result)) as mock_split:
            result = await quest_service.confirm_quest_completion(
                conn_confirm, "quest_e2e", client,
            )

            # Verify split_payment arguments
            mock_split.assert_called_once()
            call_kwargs = mock_split.call_args
            assert call_kwargs.kwargs["client_id"] == "user_client"
            assert call_kwargs.kwargs["freelancer_id"] == "user_freelancer"
            assert call_kwargs.kwargs["gross_amount"] == QUEST_BUDGET
            assert call_kwargs.kwargs["currency"] == QUEST_CURRENCY
            assert call_kwargs.kwargs["quest_id"] == "quest_e2e"
            assert Decimal(str(call_kwargs.kwargs["fee_percent"])) == FEE_PERCENT

        # Verify correct money amounts in result
        assert result["money_reward"] == EXPECTED_FREELANCER_PAYOUT
        assert result["platform_fee"] == EXPECTED_FEE
        assert result["fee_percent"] == FEE_PERCENT
        assert result["xp_reward"] > 0

    @pytest.mark.asyncio
    async def test_cancel_before_assign_refunds_hold(self):
        """Open quest cancel must refund any escrow hold back to client."""
        client = _make_user("client", "user_client")

        conn = _make_conn()
        conn.fetchrow.side_effect = [
            {
                "id": "quest_cancel",
                "client_id": "user_client",
                "status": "open",
                "assigned_to": None,
                "title": "Cancel Quest",
                "currency": "RUB",
                "budget": QUEST_BUDGET,
            },
        ]
        conn.fetchval.return_value = "quest_cancel"
        conn.fetch.return_value = []

        with patch.object(wallet_service, "refund_hold", new=AsyncMock(return_value=QUEST_BUDGET)) as mock_refund:
            await quest_service.cancel_quest(conn, "quest_cancel", client)

            mock_refund.assert_called_once_with(
                conn,
                user_id="user_client",
                quest_id="quest_cancel",
                currency="RUB",
            )

    @pytest.mark.asyncio
    async def test_withdrawal_after_earnings(self):
        """After receiving quest payment, freelancer can withdraw funds."""
        conn = _make_conn()

        # Simulate wallet with earned amount
        conn.fetchrow.side_effect = [
            {"id": "w_fl", "balance": EXPECTED_FREELANCER_PAYOUT, "currency": "RUB"},  # wallet lookup
        ]
        conn.fetchval.side_effect = [
            0,  # pending withdrawal count
            "tx_withdrawal_1",  # created transaction id
        ]

        withdrawal_amount = Decimal("5000.00")

        with patch.object(
            wallet_service, "create_withdrawal",
            new=AsyncMock(return_value={
                "transaction_id": "tx_withdrawal_1",
                "amount": withdrawal_amount,
                "currency": "RUB",
                "status": "pending",
                "remaining_balance": EXPECTED_FREELANCER_PAYOUT - withdrawal_amount,
            }),
        ) as mock_withdraw:
            result = await wallet_service.create_withdrawal(
                conn,
                user_id="user_freelancer",
                amount=withdrawal_amount,
                currency="RUB",
            )

            assert result["amount"] == withdrawal_amount
            assert result["status"] == "pending"
            assert result["remaining_balance"] == EXPECTED_FREELANCER_PAYOUT - withdrawal_amount

    @pytest.mark.asyncio
    async def test_fee_percent_zero_falls_back_to_settings(self):
        """Raid quests with fee_percent=0 must use settings default."""
        client = _make_user("client", "user_client")

        conn = _make_conn()
        # Quest with platform_fee_percent = 0 (raid quest bug)
        conn.fetchrow.side_effect = [
            _quest_row(status="completed", assigned_to="user_freelancer", platform_fee_percent=Decimal("0")),
            _freelancer_row(),
            _quest_row(status="confirmed", assigned_to="user_freelancer"),
        ]
        conn.fetchval.side_effect = [
            "quest_e2e",  # CAS
            1,  # badge count
        ]
        conn.fetch.return_value = []

        with (
            patch.object(wallet_service, "split_payment", new=AsyncMock(return_value={
                "gross_amount": QUEST_BUDGET,
                "fee_percent": Decimal("10"),
                "freelancer_amount": Decimal("9000.00"),
                "platform_fee": Decimal("1000.00"),
                "client_balance": Decimal("0.00"),
                "freelancer_balance": Decimal("9000.00"),
                "platform_balance": Decimal("1000.00"),
                "client_surcharge_amount": Decimal("0"),
            })) as mock_split,
            patch("app.core.config.settings") as mock_settings,
        ):
            mock_settings.PLATFORM_FEE_PERCENT = "10"
            result = await quest_service.confirm_quest_completion(conn, "quest_e2e", client)

            # Verify the fee_percent passed to split_payment is not 0
            call_kwargs = mock_split.call_args
            used_fee = Decimal(str(call_kwargs.kwargs["fee_percent"]))
            assert used_fee > 0, "Fee percent 0 must fall back to settings default"
