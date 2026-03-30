"""Unit tests for dispute_service.py — mocked asyncpg connection."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import dispute_service
from app.models.dispute import DisputeStatus, ResolutionType


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_conn(in_transaction=True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_transaction)
    return conn


def _now():
    return datetime.now(timezone.utc)


def _dispute_row(
    status="open",
    initiator_id="freelancer_1",
    respondent_id="client_1",
    resolution_type=None,
    partial_percent=None,
):
    now = _now()
    return {
        "id": "dis_test123456",
        "quest_id": "quest_1",
        "initiator_id": initiator_id,
        "respondent_id": respondent_id,
        "reason": "Client not responding",
        "response_text": None,
        "status": status,
        "resolution_type": resolution_type,
        "partial_percent": partial_percent,
        "resolution_note": None,
        "moderator_id": None,
        "auto_escalate_at": now + timedelta(hours=72),
        "created_at": now,
        "responded_at": None,
        "escalated_at": None,
        "resolved_at": None,
    }


def _quest_row(status="completed", assigned_to="freelancer_1"):
    return {
        "id": "quest_1",
        "title": "Test Quest",
        "client_id": "client_1",
        "assigned_to": assigned_to,
        "status": status,
        "budget": "1000.00",
        "currency": "RUB",
        "platform_fee_percent": "10.0",
    }


# ─────────────────────────────────────────────────────────────────────
# open_dispute
# ─────────────────────────────────────────────────────────────────────

class TestOpenDispute:
    @pytest.mark.asyncio
    async def test_requires_transaction(self):
        conn = _make_conn(in_transaction=False)
        with pytest.raises(RuntimeError, match="transaction"):
            await dispute_service.open_dispute(
                conn, quest_id="quest_1", initiator_id="user_1", reason="Test reason here"
            )

    @pytest.mark.asyncio
    async def test_quest_not_found_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None  # quest not found
        with pytest.raises(ValueError, match="Quest not found"):
            await dispute_service.open_dispute(
                conn, quest_id="bad_id", initiator_id="user_1", reason="Test reason here"
            )

    @pytest.mark.asyncio
    async def test_non_assignee_raises_permission_error(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(assigned_to="other_freelancer")
        with pytest.raises(PermissionError, match="Only the assigned freelancer"):
            await dispute_service.open_dispute(
                conn, quest_id="quest_1", initiator_id="freelancer_1", reason="Test reason here"
            )

    @pytest.mark.asyncio
    async def test_wrong_quest_status_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="open", assigned_to="freelancer_1")
        with pytest.raises(ValueError, match="Disputes can only be opened"):
            await dispute_service.open_dispute(
                conn, quest_id="quest_1", initiator_id="freelancer_1", reason="Test reason here"
            )

    @pytest.mark.asyncio
    async def test_existing_active_dispute_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="completed", assigned_to="freelancer_1")
        conn.fetchval.side_effect = [
            "dis_existing",  # existing active dispute check
        ]
        with pytest.raises(ValueError, match="active dispute already exists"):
            await dispute_service.open_dispute(
                conn, quest_id="quest_1", initiator_id="freelancer_1", reason="Test reason here"
            )

    @pytest.mark.asyncio
    async def test_happy_path(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(status="completed", assigned_to="freelancer_1"),  # SELECT quest
            _dispute_row(),  # INSERT dispute RETURNING *
        ]
        conn.fetchval.side_effect = [
            None,       # no active dispute
            "quest_1",  # UPDATE quest RETURNING id
        ]
        conn.execute = AsyncMock()

        with patch("app.services.dispute_service.notification_service") as mock_notif:
            mock_notif.create_notification = AsyncMock()
            result = await dispute_service.open_dispute(
                conn,
                quest_id="quest_1",
                initiator_id="freelancer_1",
                reason="Test reason here",
            )

        assert result.status == DisputeStatus.open
        assert result.quest_id == "quest_1"


# ─────────────────────────────────────────────────────────────────────
# respond_dispute
# ─────────────────────────────────────────────────────────────────────

class TestRespondDispute:
    @pytest.mark.asyncio
    async def test_not_respondent_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _dispute_row(status="open", respondent_id="client_1")
        with pytest.raises(PermissionError):
            await dispute_service.respond_dispute(
                conn, dispute_id="dis_test", user_id="someone_else", response_text="My response here"
            )

    @pytest.mark.asyncio
    async def test_wrong_status_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _dispute_row(status="escalated", respondent_id="client_1")
        with pytest.raises(ValueError, match="not open"):
            await dispute_service.respond_dispute(
                conn, dispute_id="dis_test", user_id="client_1", response_text="My response here"
            )

    @pytest.mark.asyncio
    async def test_happy_path(self):
        conn = _make_conn()
        dispute = _dispute_row(status="open", respondent_id="client_1")
        responded = {**dispute, "status": "responded", "response_text": "My response here"}
        conn.fetchrow.side_effect = [dispute, responded]

        with patch("app.services.dispute_service.notification_service") as mock_notif:
            mock_notif.create_notification = AsyncMock()
            result = await dispute_service.respond_dispute(
                conn, dispute_id="dis_test", user_id="client_1", response_text="My response here"
            )

        assert result.status == DisputeStatus.responded


# ─────────────────────────────────────────────────────────────────────
# escalate_dispute
# ─────────────────────────────────────────────────────────────────────

class TestEscalateDispute:
    @pytest.mark.asyncio
    async def test_non_party_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _dispute_row(
            status="open", initiator_id="f1", respondent_id="c1"
        )
        with pytest.raises(PermissionError):
            await dispute_service.escalate_dispute(
                conn, dispute_id="dis_test", user_id="outsider"
            )

    @pytest.mark.asyncio
    async def test_already_resolved_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _dispute_row(status="resolved")
        with pytest.raises(ValueError, match="Cannot escalate"):
            await dispute_service.escalate_dispute(
                conn, dispute_id="dis_test", user_id="freelancer_1"
            )

    @pytest.mark.asyncio
    async def test_happy_path(self):
        conn = _make_conn()
        base = _dispute_row(status="responded")
        escalated = {**base, "status": "escalated"}
        conn.fetchrow.side_effect = [base, escalated]
        conn.fetch.return_value = [{"id": "admin_1"}]  # admins list

        with patch("app.services.dispute_service.notification_service") as mock_notif:
            mock_notif.create_notification = AsyncMock()
            result = await dispute_service.escalate_dispute(
                conn, dispute_id="dis_test", user_id="freelancer_1"
            )

        assert result.status == DisputeStatus.escalated


# ─────────────────────────────────────────────────────────────────────
# resolve_dispute
# ─────────────────────────────────────────────────────────────────────

class TestResolveDispute:
    @pytest.mark.asyncio
    async def test_non_escalated_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _dispute_row(status="open")
        with pytest.raises(ValueError, match="Only escalated"):
            await dispute_service.resolve_dispute(
                conn, dispute_id="dis_test", moderator_id="admin_1",
                resolution_type=ResolutionType.refund, resolution_note="Test note"
            )

    @pytest.mark.asyncio
    async def test_second_resolution_attempt_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _dispute_row(status="resolved")

        with pytest.raises(ValueError, match="Only escalated disputes can be resolved"):
            await dispute_service.resolve_dispute(
                conn,
                dispute_id="dis_test",
                moderator_id="admin_1",
                resolution_type=ResolutionType.partial,
                resolution_note="Too late",
                partial_percent=50.0,
            )

    @pytest.mark.asyncio
    async def test_partial_without_percent_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _dispute_row(status="escalated")
        with pytest.raises(ValueError, match="partial_percent"):
            await dispute_service.resolve_dispute(
                conn, dispute_id="dis_test", moderator_id="admin_1",
                resolution_type=ResolutionType.partial, resolution_note="Test note",
                partial_percent=None,
            )

    @pytest.mark.asyncio
    async def test_resolve_refund(self):
        conn = _make_conn()
        base = _dispute_row(status="escalated")
        quest = _quest_row(status="disputed")
        resolved = {**base, "status": "resolved", "resolution_type": "refund"}
        conn.fetchrow.side_effect = [base, quest, resolved]

        with (
            patch("app.services.dispute_service.wallet_service") as mock_wallet,
            patch("app.services.dispute_service.notification_service") as mock_notif,
        ):
            mock_wallet.refund_hold = AsyncMock(return_value=1000)
            mock_notif.create_notification = AsyncMock()
            conn.execute = AsyncMock()
            result = await dispute_service.resolve_dispute(
                conn, dispute_id="dis_test", moderator_id="admin_1",
                resolution_type=ResolutionType.refund, resolution_note="Client wins"
            )

        assert result.status == DisputeStatus.resolved
        assert result.resolution_type == ResolutionType.refund
        mock_wallet.refund_hold.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_refund_fails_closed_without_hold(self):
        conn = _make_conn()
        base = _dispute_row(status="escalated")
        quest = _quest_row(status="disputed")
        conn.fetchrow.side_effect = [base, quest]

        with patch("app.services.dispute_service.wallet_service") as mock_wallet:
            mock_wallet.refund_hold = AsyncMock(return_value=None)
            conn.execute = AsyncMock()

            with pytest.raises(ValueError, match="No active escrow hold found"):
                await dispute_service.resolve_dispute(
                    conn,
                    dispute_id="dis_test",
                    moderator_id="admin_1",
                    resolution_type=ResolutionType.refund,
                    resolution_note="Client wins",
                )

    @pytest.mark.asyncio
    async def test_resolve_freelancer(self):
        conn = _make_conn()
        base = _dispute_row(status="escalated")
        quest = _quest_row(status="disputed")
        resolved = {**base, "status": "resolved", "resolution_type": "freelancer"}
        freelancer_row = {
            "id": "freelancer_1", "xp": 100, "level": 1, "grade": "novice",
            "stat_points": 0, "stats_int": 10, "stats_dex": 10, "stats_cha": 10,
            "character_class": "warrior"
        }
        conn.fetchrow.side_effect = [base, quest, freelancer_row, resolved]

        with (
            patch("app.services.dispute_service.wallet_service") as mock_wallet,
            patch("app.services.dispute_service.notification_service") as mock_notif,
            patch("app.services.dispute_service.class_service") as mock_class,
            patch("app.services.dispute_service.trust_score_service") as mock_trust,
            patch("app.services.dispute_service.badge_service") as mock_badge,
        ):
            mock_wallet.split_payment = AsyncMock(return_value={})
            mock_notif.create_notification = AsyncMock()
            mock_class.add_class_xp = AsyncMock()
            mock_trust.refresh_trust_score = AsyncMock()
            mock_badge.check_and_award = AsyncMock(return_value=MagicMock(newly_earned=[]))
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(return_value=0)
            result = await dispute_service.resolve_dispute(
                conn, dispute_id="dis_test", moderator_id="admin_1",
                resolution_type=ResolutionType.freelancer, resolution_note="Freelancer wins"
            )

        assert result.status == DisputeStatus.resolved
        assert result.resolution_type == ResolutionType.freelancer
        mock_wallet.split_payment.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_partial(self):
        conn = _make_conn()
        base = _dispute_row(status="escalated")
        quest = _quest_row(status="disputed")
        resolved = {**base, "status": "resolved", "resolution_type": "partial", "partial_percent": "60.0"}
        freelancer_row = {
            "id": "freelancer_1", "xp": 100, "level": 1, "grade": "novice",
            "stat_points": 0, "stats_int": 10, "stats_dex": 10, "stats_cha": 10,
            "character_class": "warrior"
        }
        conn.fetchrow.side_effect = [base, quest, freelancer_row, resolved]

        with (
            patch("app.services.dispute_service.wallet_service") as mock_wallet,
            patch("app.services.dispute_service.notification_service") as mock_notif,
            patch("app.services.dispute_service.class_service") as mock_class,
            patch("app.services.dispute_service.trust_score_service") as mock_trust,
            patch("app.services.dispute_service.badge_service") as mock_badge,
        ):
            mock_wallet.release_hold = AsyncMock(return_value=1000)
            mock_wallet.credit = AsyncMock(return_value=100)
            mock_notif.create_notification = AsyncMock()
            mock_class.add_class_xp = AsyncMock()
            mock_trust.refresh_trust_score = AsyncMock()
            mock_badge.check_and_award = AsyncMock(return_value=MagicMock(newly_earned=[]))
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(return_value=0)
            result = await dispute_service.resolve_dispute(
                conn, dispute_id="dis_test", moderator_id="admin_1",
                resolution_type=ResolutionType.partial, resolution_note="Split it",
                partial_percent=60.0,
            )

        assert result.status == DisputeStatus.resolved
        mock_wallet.release_hold.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_partial_locks_hold_by_currency(self):
        conn = _make_conn()
        base = _dispute_row(status="escalated")
        quest = _quest_row(status="disputed")
        resolved = {**base, "status": "resolved", "resolution_type": "partial", "partial_percent": "60.0"}
        conn.fetchrow.side_effect = [base, quest, {"id": "hold_1"}, resolved]

        with (
            patch("app.services.dispute_service.wallet_service") as mock_wallet,
            patch("app.services.dispute_service.notification_service") as mock_notif,
            patch("app.services.dispute_service.class_service") as mock_class,
            patch("app.services.dispute_service.trust_score_service") as mock_trust,
            patch("app.services.dispute_service.badge_service") as mock_badge,
        ):
            mock_wallet.release_hold = AsyncMock(return_value=1000)
            mock_wallet.credit = AsyncMock(return_value=100)
            mock_notif.create_notification = AsyncMock()
            mock_class.add_class_xp = AsyncMock()
            mock_trust.refresh_trust_score = AsyncMock()
            mock_badge.check_and_award = AsyncMock(return_value=MagicMock(newly_earned=[]))
            conn.execute = AsyncMock()
            conn.fetchval = AsyncMock(return_value=0)

            result = await dispute_service.resolve_dispute(
                conn,
                dispute_id="dis_test",
                moderator_id="admin_1",
                resolution_type=ResolutionType.partial,
                resolution_note="Split it",
                partial_percent=60.0,
            )

        assert result.status == DisputeStatus.resolved
        hold_lookup = conn.fetchrow.await_args_list[2]
        assert "currency = $3" in hold_lookup.args[0]
        assert "FOR UPDATE" in hold_lookup.args[0]
        assert hold_lookup.args[1:] == ("client_1", "quest_1", "RUB")


# ─────────────────────────────────────────────────────────────────────
# auto_escalate_overdue
# ─────────────────────────────────────────────────────────────────────

class TestAutoEscalateOverdue:
    @pytest.mark.asyncio
    async def test_no_overdue_returns_zero(self):
        conn = _make_conn()
        conn.fetch.side_effect = [
            [],              # UPDATE...RETURNING (no overdue)
        ]
        result = await dispute_service.auto_escalate_overdue(conn)
        assert result == 0

    @pytest.mark.asyncio
    async def test_escalates_overdue_disputes(self):
        conn = _make_conn()
        conn.fetch.side_effect = [
            [
                {"id": "dis_1", "initiator_id": "f1", "respondent_id": "c1"},
                {"id": "dis_2", "initiator_id": "f2", "respondent_id": "c2"},
            ],  # UPDATE...RETURNING
            [{"id": "admin_1"}],  # admin list
        ]

        with patch("app.services.dispute_service.notification_service") as mock_notif:
            mock_notif.create_notification = AsyncMock()
            result = await dispute_service.auto_escalate_overdue(conn)

        assert result == 2


# ─────────────────────────────────────────────────────────────────────
# get_dispute
# ─────────────────────────────────────────────────────────────────────

class TestGetDispute:
    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await dispute_service.get_dispute(conn, "bad_id", user_id="anyone")

    @pytest.mark.asyncio
    async def test_non_party_raises(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _dispute_row(
            initiator_id="f1", respondent_id="c1"
        )
        with pytest.raises(PermissionError):
            await dispute_service.get_dispute(conn, "dis_test", user_id="outsider")

    @pytest.mark.asyncio
    async def test_admin_can_access(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _dispute_row(
            initiator_id="f1", respondent_id="c1"
        )
        result = await dispute_service.get_dispute(
            conn, "dis_test", user_id="outsider", is_admin=True
        )
        assert result.quest_id == "quest_1"
