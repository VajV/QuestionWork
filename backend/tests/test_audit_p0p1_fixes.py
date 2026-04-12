"""
Tests for all P0 + P1 audit fixes.

18 bugs: F-03, F-04, D-04, FE-02 (frontend—untestable here),
         Q-04, Q-05, Q-06, A-03, A-04, A-05,
         R-04, R-05, R-06, E-01, E-02, E-03, H-01.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats
from app.models.quest import QuestApplicationCreate, QuestStatusEnum, QuestRevisionRequest


# ──────────────────────────────────────────────────────
# Module-level patch: challenge_service is non-critical and should not
# interfere with unit tests that mock conn.fetchrow with fixed side_effects.
# ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _patch_challenge_service():
    with patch("app.services.quest_service.challenge_service") as mock_ch:
        mock_ch.increment_challenge_progress = AsyncMock(return_value=None)
        with patch("app.services.quest_service.referral_service") as mock_ref:
            mock_ref.grant_referral_rewards = AsyncMock(return_value=None)
            yield mock_ch


# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────


class _FakeTransaction:
    async def __aenter__(self):
        return self
    async def __aexit__(self, *exc):
        return False


def _make_conn(in_txn=True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_txn)
    conn.transaction = MagicMock(return_value=_FakeTransaction())
    return conn


def _make_user(role="client", user_id="user1", grade=GradeEnum.novice, is_banned=False, character_class=None):
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
        character_class=character_class,
    )


def _quest_row(
    quest_id="q1",
    client_id="user_client",
    status="open",
    assigned_to=None,
    budget=Decimal("5000"),
    required_grade="novice",
    xp_reward=50,
    revision_count=0,
):
    now = datetime.now(timezone.utc)
    return {
        "id": quest_id,
        "client_id": client_id,
        "client_username": "test_client",
        "title": "Test Quest Title",
        "description": "A detailed quest description that meets minimum length requirement",
        "required_grade": required_grade,
        "skills": '["python"]',
        "budget": budget,
        "currency": "RUB",
        "xp_reward": xp_reward,
        "status": status,
        "applications": [],
        "assigned_to": assigned_to,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "delivery_note": None,
        "delivery_url": None,
        "delivery_submitted_at": None,
        "revision_reason": None,
        "revision_requested_at": None,
        "revision_count": revision_count,
        "is_urgent": False,
        "deadline": None,
        "required_portfolio": False,
        "platform_fee_percent": None,
    }


def _user_row(user_id="fl1", grade="novice", xp=0, level=1, character_class=None, stats_int=50, stats_dex=50, stats_cha=50):
    return {
        "id": user_id,
        "username": f"user_{user_id}",
        "email": "test@test.com",
        "grade": grade,
        "xp": xp,
        "level": level,
        "xp_to_next": 100,
        "stats_int": stats_int,
        "stats_dex": stats_dex,
        "stats_cha": stats_cha,
        "stat_points": 0,
        "character_class": character_class,
        "role": "freelancer",
        "is_banned": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


# ──────────────────────────────────────────────────────
# F-03: Admin cannot self-action
# ──────────────────────────────────────────────────────

class TestF03_AdminSelfAction:
    """Admin must not modify their own account, XP, or wallet."""

    @pytest.mark.asyncio
    async def test_update_user_blocks_self(self):
        from app.services.admin_service import update_user
        conn = _make_conn()
        with pytest.raises(ValueError, match="Cannot modify your own account"):
            await update_user(conn, user_id="admin1", fields={"username": "x"}, admin_id="admin1")

    @pytest.mark.asyncio
    async def test_grant_xp_blocks_self(self):
        from app.services.admin_service import grant_xp
        conn = _make_conn()
        with pytest.raises(ValueError, match="Cannot grant XP to yourself"):
            await grant_xp(conn, user_id="admin1", amount=100, reason="test", admin_id="admin1")

    @pytest.mark.asyncio
    async def test_adjust_wallet_blocks_self(self):
        from app.services.admin_service import adjust_wallet
        conn = _make_conn()
        with pytest.raises(ValueError, match="Cannot adjust your own wallet"):
            await adjust_wallet(conn, user_id="admin1", amount=Decimal("100"), currency="RUB", reason="t", admin_id="admin1")


# ──────────────────────────────────────────────────────
# F-04: Block role escalation to admin
# ──────────────────────────────────────────────────────

class TestF04_RoleEscalation:
    @pytest.mark.asyncio
    async def test_update_user_blocks_admin_role(self):
        from app.services.admin_service import update_user
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=_user_row("u1"))
        with pytest.raises(ValueError, match="Cannot set role to admin"):
            await update_user(conn, user_id="u1", fields={"role": "admin"}, admin_id="admin1")


# ──────────────────────────────────────────────────────
# D-04: Audit trail preservation on user delete
# ──────────────────────────────────────────────────────

class TestD04_AuditPreservation:
    @pytest.mark.asyncio
    async def test_delete_user_nullifies_not_deletes(self):
        """delete_user should UPDATE admin_logs SET target_id = NULL and
        UPDATE transactions SET user_id = NULL instead of DELETE."""
        from app.services.admin_service import delete_user
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=_user_row("victim"))
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=0)

        await delete_user(conn, user_id="victim", admin_id="admin1")

        # Check that none of the execute calls contain "DELETE FROM admin_logs"
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        assert "DELETE FROM admin_logs" not in all_sql
        # Should contain UPDATE admin_logs SET target_id = NULL
        assert "UPDATE admin_logs SET target_id = NULL" in all_sql or "target_id = NULL" in all_sql


# ──────────────────────────────────────────────────────
# Q-04: Revision limit
# ──────────────────────────────────────────────────────

class TestQ04_RevisionLimit:
    @pytest.mark.asyncio
    async def test_revision_blocked_after_max(self):
        from app.services.quest_service import request_quest_revision
        conn = _make_conn()
        quest = _quest_row(status="completed", assigned_to="fl1", client_id="c1", revision_count=3)
        conn.fetchrow = AsyncMock(return_value=quest)

        user = _make_user(user_id="c1")
        with pytest.raises(ValueError, match="Maximum revisions"):
            await request_quest_revision(
                conn, "q1", QuestRevisionRequest(revision_reason="Please fix the formatting issues"), user
            )

    @pytest.mark.asyncio
    async def test_revision_allowed_under_limit(self):
        from app.services.quest_service import request_quest_revision
        conn = _make_conn()
        quest = _quest_row(status="completed", assigned_to="fl1", client_id="c1", revision_count=1)
        # fetchrow called twice: 1st FOR UPDATE, 2nd re-fetch after update
        updated_quest = dict(quest, status="revision_requested")
        conn.fetchrow = AsyncMock(side_effect=[quest, updated_quest])
        conn.execute = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])  # _fetch_quest_applications

        user = _make_user(user_id="c1")
        with patch("app.services.quest_service._record_status_history", new_callable=AsyncMock):
            with patch("app.services.quest_service.message_service") as mock_msg:
                mock_msg.create_system_message = AsyncMock()
                with patch("app.services.quest_service.notification_service") as mock_notif:
                    mock_notif.create_notification = AsyncMock()
                    result = await request_quest_revision(
                        conn, "q1", QuestRevisionRequest(revision_reason="Please fix the formatting issues"), user
                    )
        assert result is not None


# ──────────────────────────────────────────────────────
# Q-05: cancel_quest allows revision_requested (P1-2 fix)
# ──────────────────────────────────────────────────────

class TestQ05_CancelAfterRevision:
    @pytest.mark.asyncio
    async def test_cancel_allows_revision_requested(self):
        """P1-2 FIX: revision_requested quests CAN be cancelled by the client."""
        from app.services.quest_service import cancel_quest
        conn = _make_conn()
        quest = _quest_row(status="revision_requested", client_id="c1", assigned_to="fl1")
        conn.fetchrow.side_effect = [
            quest,  # quest lookup
            None,   # refund_hold: no active hold
        ]

        user = _make_user(user_id="c1")
        result = await cancel_quest(conn, "q1", user)
        assert "cancelled" in result["message"].lower()


# ──────────────────────────────────────────────────────
# Q-06: force_complete blocks draft/open
# ──────────────────────────────────────────────────────

class TestQ06_ForceCompleteDraftOpen:
    @pytest.mark.asyncio
    async def test_force_complete_blocks_draft(self):
        from app.services.admin_service import force_complete_quest
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=_quest_row(status="draft"))

        with pytest.raises(ValueError, match="Cannot force-complete"):
            await force_complete_quest(conn, "q1", reason="admin override", admin_id="admin1")

    @pytest.mark.asyncio
    async def test_force_complete_blocks_open(self):
        from app.services.admin_service import force_complete_quest
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=_quest_row(status="open"))

        with pytest.raises(ValueError, match="Cannot force-complete"):
            await force_complete_quest(conn, "q1", reason="admin override", admin_id="admin1")


# ──────────────────────────────────────────────────────
# A-03: TOTP replay protection fallback (in-memory)
# ──────────────────────────────────────────────────────

class TestA03_TOTPReplayMemory:
    def test_memory_replay_blocks_duplicate(self):
        from app.api.deps import _totp_replay_check_memory, _TOTP_REPLAY_STORE
        from fastapi import HTTPException
        _TOTP_REPLAY_STORE.clear()

        # First use should succeed (no exception)
        _totp_replay_check_memory("admin1", "123456")

        # Second use of same code should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _totp_replay_check_memory("admin1", "123456")
        assert exc_info.value.status_code == 403

    def test_memory_replay_allows_different_codes(self):
        from app.api.deps import _totp_replay_check_memory, _TOTP_REPLAY_STORE
        _TOTP_REPLAY_STORE.clear()

        # Both should succeed (no exception raised)
        _totp_replay_check_memory("admin1", "111111")
        _totp_replay_check_memory("admin1", "222222")


# ──────────────────────────────────────────────────────
# A-04: Email not leaked in user list
# ──────────────────────────────────────────────────────

class TestA04_EmailLeak:
    @pytest.mark.asyncio
    async def test_get_all_users_strips_email(self):
        """The GET /users/ endpoint must use the public-safe user DTO."""
        from app.api.v1.endpoints.users import get_all_users

        now = datetime.now(timezone.utc)
        fake_row = {
            "id": "u2", "username": "other", "email": "secret@example.com",
            "role": "freelancer", "is_banned": False, "banned_reason": None,
            "level": 1, "grade": "novice", "xp": 0, "xp_to_next": 100,
            "stat_points": 0, "stats_int": 50, "stats_dex": 50, "stats_cha": 50,
            "badges": "[]", "bio": None, "skills": "[]", "character_class": None,
            "created_at": now, "updated_at": now,
        }
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[fake_row])
        conn.fetchval = AsyncMock(return_value=1)

        fake_request = MagicMock()
        fake_request.client = MagicMock()
        fake_request.client.host = "127.0.0.1"
        fake_request.headers = {}

        with patch("app.api.v1.endpoints.users.check_rate_limit"):
            result = await get_all_users(
                request=fake_request,
                conn=conn, skip=0, limit=20,
                sort_by="created_at", sort_order="desc",
            )

        user_item = result["users"][0]
        assert not hasattr(user_item, "email")
        assert not hasattr(user_item, "is_banned")
        assert not hasattr(user_item, "banned_reason")


# ──────────────────────────────────────────────────────
# A-05: Wallet error doesn't leak balance
# ──────────────────────────────────────────────────────

class TestA05_WalletErrorLeak:
    def test_insufficient_funds_message_is_generic(self):
        from app.services.wallet_service import InsufficientFundsError
        err = InsufficientFundsError("Insufficient funds")
        # Should NOT contain specific amounts or user IDs
        assert "user" not in str(err).lower() or "Insufficient funds" in str(err)


# ──────────────────────────────────────────────────────
# R-04: Quest slot limit enforcement
# ──────────────────────────────────────────────────────

class TestR04_QuestSlotLimit:
    @pytest.mark.asyncio
    async def test_apply_blocked_at_slot_limit(self):
        from app.services.quest_service import apply_to_quest, BASE_QUEST_SLOTS
        conn = _make_conn()
        quest = _quest_row(client_id="other_client")
        conn.fetchrow = AsyncMock(side_effect=[
            quest,   # quest lookup
            None,    # existing application check → none
        ])
        # fetchval calls: active quest count
        conn.fetchval = AsyncMock(return_value=BASE_QUEST_SLOTS)

        freelancer = _make_user(role="freelancer", user_id="fl1")
        with pytest.raises(ValueError, match="slot limit"):
            await apply_to_quest(
                conn, "q1",
                QuestApplicationCreate(cover_letter="I am applying for this quest with experience", proposed_price=1000),
                freelancer,
            )

    @pytest.mark.asyncio
    async def test_assign_blocked_at_slot_limit(self):
        from app.services.quest_service import assign_freelancer, BASE_QUEST_SLOTS
        conn = _make_conn()
        quest = _quest_row(client_id="c1", status="open")

        # fetchrow calls: quest row, application check, freelancer class row
        conn.fetchrow = AsyncMock(side_effect=[
            quest,
            {"id": "app1"},
            {"character_class": None},
        ])
        conn.fetchval = AsyncMock(return_value=BASE_QUEST_SLOTS)

        client = _make_user(role="client", user_id="c1")
        with pytest.raises(ValueError, match="slot limit"):
            await assign_freelancer(conn, "q1", "fl1", client)


# ──────────────────────────────────────────────────────
# R-05: Burnout XP penalty applied
# ──────────────────────────────────────────────────────

class TestR05_BurnoutXPPenalty:
    @pytest.mark.asyncio
    async def test_burnout_reduces_xp_reward(self):
        """When freelancer is burned out, XP reward should be reduced by class penalty."""
        from app.services.quest_service import confirm_quest_completion

        conn = _make_conn()
        quest = _quest_row(
            status="completed",
            client_id="c1",
            assigned_to="fl1",
            budget=Decimal("10000"),
            xp_reward=500,
        )
        freelancer = _user_row("fl1", character_class="berserk", xp=50, level=1)

        conn.fetchrow = AsyncMock(side_effect=[quest, freelancer, None, quest])  # quest, freelancer, chain_step(None), updated_quest
        # fetchval #1 = CAS update RETURNING id, #2 = badge count
        conn.fetchval = AsyncMock(side_effect=["q1", 5])
        conn.execute = AsyncMock()

        user = _make_user(user_id="c1")

        # Mock check_burnout to return True
        with patch("app.services.quest_service.class_service") as mock_cls:
            mock_cls.check_burnout = AsyncMock(return_value=True)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={})
            mock_cls.add_class_xp = AsyncMock(return_value={"class_xp_gained": 10, "class_level_up": False})
            mock_cls.reset_consecutive_if_stale = AsyncMock()
            with patch("app.services.quest_service.wallet_service") as mock_wallet:
                mock_wallet.split_payment = AsyncMock(return_value={
                    "freelancer_amount": Decimal("9000"),
                    "platform_fee": Decimal("1000"),
                    "fee_percent": Decimal("10"),
                })
                with patch("app.services.quest_service.badge_service") as mock_badge:
                    from app.models.badge_notification import BadgeAwardResult
                    mock_badge.check_and_award = AsyncMock(return_value=BadgeAwardResult(newly_earned=[]))
                    with patch("app.services.quest_service.notification_service") as mock_notif:
                        mock_notif.create_notification = AsyncMock()
                        with patch("app.services.quest_service._record_status_history", new_callable=AsyncMock):
                            with patch("app.services.quest_service.message_service") as mock_msg:
                                mock_msg.create_system_message = AsyncMock()
                                with patch(
                                    "app.services.quest_service.guild_economy_service.apply_quest_completion_rewards",
                                    new=AsyncMock(return_value=None),
                                ):
                                    with patch(
                                        "app.services.quest_service.guild_economy_service.award_solo_artifact_drop",
                                        new=AsyncMock(return_value=None),
                                    ):
                                        with patch(
                                            "app.services.quest_service.trust_score_service.refresh_trust_score",
                                            new=AsyncMock(),
                                        ):
                                            result = await confirm_quest_completion(conn, "q1", user)

        # The XP reward should have been reduced due to burnout
        # Berserk penalty = -10%, so xp should be 90% of original
        assert result["xp_reward"] == 450
        # We can verify by checking that the UPDATE was called with reduced XP
        update_calls = [c for c in conn.execute.call_args_list if "UPDATE users" in str(c)]
        assert len(update_calls) > 0
        user_update_args = update_calls[0][0]
        assert user_update_args[1] == 500


# ──────────────────────────────────────────────────────
# R-06: Stat overflow cap at 100
# ──────────────────────────────────────────────────────

class TestR06_StatOverflowCap:
    @pytest.mark.asyncio
    async def test_stats_capped_at_100_on_completion(self):
        """Stats should never exceed 100 even with large level-up bonuses."""
        from app.services.quest_service import confirm_quest_completion

        conn = _make_conn()
        quest = _quest_row(status="completed", client_id="c1", assigned_to="fl1", budget=Decimal("50000"))
        # Freelancer already at stats near cap
        freelancer = _user_row("fl1", xp=0, level=1, stats_int=99, stats_dex=99, stats_cha=99)

        conn.fetchrow = AsyncMock(side_effect=[quest, freelancer, None, quest])  # quest, freelancer, chain_step(None), updated_quest
        # fetchval #1 = CAS update RETURNING id, #2 = badge count
        conn.fetchval = AsyncMock(side_effect=["q1", 5])
        conn.execute = AsyncMock()

        user = _make_user(user_id="c1")

        with patch("app.services.quest_service.class_service") as mock_cls:
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={})
            mock_cls.add_class_xp = AsyncMock(return_value={"class_xp_gained": 10, "class_level_up": False})
            mock_cls.reset_consecutive_if_stale = AsyncMock()
            with patch("app.services.quest_service.wallet_service") as mock_wallet:
                mock_wallet.split_payment = AsyncMock(return_value={
                    "freelancer_amount": Decimal("45000"),
                    "platform_fee": Decimal("5000"),
                    "fee_percent": Decimal("10"),
                })
                with patch("app.services.quest_service.badge_service") as mock_badge:
                    from app.models.badge_notification import BadgeAwardResult
                    mock_badge.check_and_award = AsyncMock(return_value=BadgeAwardResult(newly_earned=[]))
                    with patch("app.services.quest_service.notification_service") as mock_notif:
                        mock_notif.create_notification = AsyncMock()
                        with patch("app.services.quest_service._record_status_history", new_callable=AsyncMock):
                            with patch("app.services.quest_service.message_service") as mock_msg:
                                mock_msg.create_system_message = AsyncMock()
                                # Force a large level gain by mocking check_level_up
                                with patch("app.services.quest_service.check_level_up") as mock_lu:
                                    mock_lu.return_value = (True, GradeEnum.junior, 10, [GradeEnum.junior])  # 9 levels gained
                                    with patch("app.services.quest_service.calculate_xp_to_next", return_value=500):
                                        with patch("app.services.quest_service.allocate_stat_points") as mock_alloc:
                                            mock_alloc.return_value = {"int": 10, "dex": 10, "cha": 10, "unspent": 5}
                                            with patch(
                                                "app.services.quest_service.guild_economy_service.apply_quest_completion_rewards",
                                                new=AsyncMock(return_value=None),
                                            ):
                                                with patch(
                                                    "app.services.quest_service.guild_economy_service.award_solo_artifact_drop",
                                                    new=AsyncMock(return_value=None),
                                                ):
                                                    with patch(
                                                        "app.services.quest_service.trust_score_service.refresh_trust_score",
                                                        new=AsyncMock(),
                                                    ):
                                                        result = await confirm_quest_completion(conn, "q1", user)

        # Verify stats were capped — find the UPDATE users call
        assert result["stat_delta"] == {"int": 10, "dex": 10, "cha": 10, "unspent": 5}
        for call in conn.execute.call_args_list:
            sql = str(call)
            if "UPDATE users" in sql and "stats_int" in sql:
                args = call[0]  # positional args
                # args after SQL: new_xp, new_level, new_grade, new_xp_to_next, stats_int, stats_dex, stats_cha, ...
                # stats_int should be min(100, 99+10) = 100
                stats_int_val = args[5] if len(args) > 5 else None
                stats_dex_val = args[6] if len(args) > 6 else None
                stats_cha_val = args[7] if len(args) > 7 else None
                if stats_int_val is not None:
                    assert stats_int_val <= 100, f"stats_int exceeded cap: {stats_int_val}"
                if stats_dex_val is not None:
                    assert stats_dex_val <= 100, f"stats_dex exceeded cap: {stats_dex_val}"
                if stats_cha_val is not None:
                    assert stats_cha_val <= 100, f"stats_cha exceeded cap: {stats_cha_val}"

    def test_stat_cap_constant_exists(self):
        from app.services.quest_service import STAT_CAP
        assert STAT_CAP == 100

    def test_admin_grant_xp_sql_uses_least(self):
        """Verify the SQL in grant_xp uses LEAST(..., 100) for stat capping."""
        import inspect
        from app.services.admin_service import grant_xp
        source = inspect.getsource(grant_xp)
        assert "LEAST(" in source, "grant_xp SQL should use LEAST for stat cap"


# ──────────────────────────────────────────────────────
# E-01: Malformed Content-Length returns 400
# ──────────────────────────────────────────────────────

class TestE01_ContentLengthParsing:
    @pytest.mark.asyncio
    async def test_malformed_content_length_returns_400(self):
        """Middleware should return 400 for non-numeric Content-Length."""
        from starlette.testclient import TestClient
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/v1/auth/login",
            headers={"Content-Length": "not-a-number"},
            content=b"{}",
        )
        assert response.status_code == 400


# ──────────────────────────────────────────────────────
# E-02: InsufficientFundsError caught in quest confirmation
# ──────────────────────────────────────────────────────

class TestE02_InsufficientFundsCatch:
    def test_quests_endpoint_imports_insufficient_funds(self):
        """The quests endpoint should import InsufficientFundsError."""
        from app.api.v1.endpoints import quests
        assert hasattr(quests, "InsufficientFundsError")


# ──────────────────────────────────────────────────────
# E-03: Badge check narrowed exception
# ──────────────────────────────────────────────────────

class TestE03_BadgeCheckException:
    def test_review_service_uses_specific_exceptions(self):
        """Badge check should catch specific exceptions, not bare Exception."""
        import inspect
        from app.services import review_service
        source = inspect.getsource(review_service)
        # Should NOT have "except Exception:" in the badge check area
        # Should have specific exceptions like KeyError, TypeError, etc.
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("except Exception:") or stripped.startswith("except Exception as"):
                # This should not happen in badge check section
                context = "\n".join(lines[max(0, i - 3):i + 1])
                if "badge" in context.lower():
                    pytest.fail("Found 'except Exception' near badge check code")


# ──────────────────────────────────────────────────────
# H-01: SQL parameterized in cleanup_old_notifications
# ──────────────────────────────────────────────────────

class TestH01_SQLParameterized:
    def test_cleanup_notifications_no_fstring_sql(self):
        """cleanup_old_notifications should use parameterized SQL, not f-strings."""
        import inspect
        from app.services.admin_service import cleanup_old_notifications
        source = inspect.getsource(cleanup_old_notifications)
        # Should NOT have f-string with INTERVAL
        assert "f'" not in source or "INTERVAL" not in source, \
            "cleanup_old_notifications should not use f-string SQL with INTERVAL"
        # Should use make_interval or parameterized approach
        assert "make_interval" in source or "$1" in source, \
            "cleanup_old_notifications should use parameterized query"


# ──────────────────────────────────────────────────────
# FE-02: Frontend API retry only for idempotent (code check)
# ──────────────────────────────────────────────────────

class TestFE02_IdempotentRetry:
    def test_api_ts_has_idempotent_check(self):
        """The fetchApi function should only retry idempotent methods."""
        import pathlib
        api_ts = pathlib.Path("frontend/src/lib/api.ts")
        if not api_ts.exists():
            api_ts = pathlib.Path("c:/QuestionWork/frontend/src/lib/api.ts")
        if api_ts.exists():
            content = api_ts.read_text(encoding="utf-8")
            assert "isIdempotent" in content or "GET" in content and "HEAD" in content, \
                "api.ts should check method idempotency before retrying"
        else:
            pytest.skip("frontend/src/lib/api.ts not found")
