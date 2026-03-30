"""Tests for quest_service — unit tests with mocked asyncpg connection."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from decimal import Decimal

import contextlib

from app.db import session
from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats
from app.models.quest import (
    QuestApplicationCreate,
    QuestCompletionCreate,
    QuestCreate,
    QuestRevisionRequest,
    QuestStatusEnum,
    QuestUpdate,
)
from app.services import quest_service
from app.db.models import QuestORM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTransaction:
    """Minimal async context manager that mimics asyncpg Transaction."""
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _make_conn():
    """Create a mock asyncpg connection with async methods."""
    conn = AsyncMock()
    # AsyncMock auto-attrs are truthy, so is_in_transaction passes _assert_in_transaction
    conn.is_in_transaction = MagicMock(return_value=True)
    # conn.transaction() must return an async context manager, not a coroutine
    conn.transaction = MagicMock(return_value=_FakeTransaction())
    return conn


@pytest.fixture(autouse=True)
def _mock_refresh_trust_score():
    with patch(
        "app.services.quest_service.trust_score_service.refresh_trust_score",
        new=AsyncMock(return_value=None),
    ):
        yield


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


def _quest_row(
    quest_id="quest_1",
    client_id="user_client",
    status="open",
    assigned_to=None,
    budget=Decimal("5000"),
    required_grade="novice",
    xp_reward=50,
):
    """Fake asyncpg Record-like dict for a quest."""
    now = datetime.now(timezone.utc)
    return {
        "id": quest_id,
        "client_id": client_id,
        "client_username": "test_client",
        "title": "Test Quest",
        "description": "A test quest description",
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
    }


def _user_row(
    user_id="user_freelancer",
    grade="novice",
    xp=0,
    level=1,
    xp_to_next=100,
    character_class=None,
):
    now = datetime.now(timezone.utc)
    return {
        "id": user_id,
        "username": "test_freelancer",
        "email": "fl@test.com",
        "password_hash": "hash",
        "role": "freelancer",
        "level": level,
        "grade": grade,
        "xp": xp,
        "xp_to_next": xp_to_next,
        "stats_int": 10,
        "stats_dex": 10,
        "stats_cha": 10,
        "stat_points": 0,
        "badges": "[]",
        "bio": None,
        "skills": "[]",
        "character_class": character_class,
        "created_at": now,
        "updated_at": now,
    }


# ---------------------------------------------------------------------------
# list_quests
# ---------------------------------------------------------------------------


class TestListQuests:
    @pytest.mark.asyncio
    async def test_empty_list(self):
        conn = _make_conn()
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        result = await quest_service.list_quests(conn, page=1, page_size=10)

        assert result.quests == []
        assert result.total == 0
        assert result.has_more is False


# ---------------------------------------------------------------------------
# get_quest_by_id
# ---------------------------------------------------------------------------


class TestGetQuestById:
    @pytest.mark.asyncio
    async def test_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None

        result = await quest_service.get_quest_by_id(conn, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row()
        conn.fetch.return_value = []  # no applications

        result = await quest_service.get_quest_by_id(conn, "quest_1")
        assert result is not None
        assert result.id == "quest_1"
        assert result.status == QuestStatusEnum.open

    @pytest.mark.asyncio
    async def test_draft_hidden_for_strangers(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="draft")
        conn.fetch.return_value = []

        stranger = _make_user("freelancer", "stranger")
        result = await quest_service.get_quest_by_id(conn, "quest_1", stranger)
        assert result is None


# ---------------------------------------------------------------------------
# create_quest
# ---------------------------------------------------------------------------


class TestQuestSchemaValidation:
    @pytest.mark.asyncio
    async def test_schema_validation_requires_platform_fee_percent(self):
        conn = AsyncMock()
        conn.fetchval.side_effect = [1, None]

        with pytest.raises(RuntimeError, match="platform_fee_percent"):
            await session._validate_required_schema(conn)


class TestQuestSchemaTruth:
    def test_quest_orm_declares_gin_index_for_skills_filtering(self):
        skill_indexes = [index for index in QuestORM.__table__.indexes if index.name == "idx_quests_skills_gin"]

        assert len(skill_indexes) == 1
        index = skill_indexes[0]
        assert [column.name for column in index.columns] == ["skills"]
        assert index.dialect_options["postgresql"]["using"] == "gin"


class TestCreateQuest:
    @pytest.mark.asyncio
    async def test_creates_quest(self):
        conn = _make_conn()
        conn.fetchval.return_value = 0  # active quest count
        user = _make_user("client")
        data = QuestCreate(
            title="New Quest Title",
            description="A sufficiently long description for validation",
            budget=5000,
            currency="RUB",
            required_grade=GradeEnum.novice,
        )

        quest = await quest_service.create_quest(conn, data, user)

        assert quest.title == "New Quest Title"
        assert quest.status == QuestStatusEnum.open
        assert quest.client_id == user.id
        assert conn.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_creates_draft_quest(self):
        conn = _make_conn()
        conn.fetchval.return_value = 0  # active quest count
        user = _make_user("client")
        data = QuestCreate(
            title="Draft Quest Title",
            description="A sufficiently long description for draft validation",
            budget=5000,
            currency="RUB",
            required_grade=GradeEnum.novice,
            status="draft",
        )

        quest = await quest_service.create_quest(conn, data, user)

        assert quest.status == QuestStatusEnum.draft
        assert conn.execute.await_count == 2


class TestDraftLifecycle:
    @pytest.mark.asyncio
    async def test_update_draft(self):
        conn = _make_conn()
        user = _make_user("client")
        conn.fetchrow.side_effect = [
            _quest_row(status="draft"),
            _quest_row(status="draft") | {"title": "Updated title"},
        ]
        conn.fetch.return_value = []

        result = await quest_service.update_quest(
            conn,
            "quest_1",
            QuestUpdate(title="Updated title"),
            user,
        )

        assert result.title == "Updated title"

    @pytest.mark.asyncio
    async def test_publish_draft(self):
        conn = _make_conn()
        user = _make_user("client")
        conn.fetchrow.side_effect = [
            _quest_row(status="draft"),
            _quest_row(status="open"),
        ]
        conn.fetch.return_value = []

        result = await quest_service.publish_quest(conn, "quest_1", user)

        assert result.status == QuestStatusEnum.open
        assert conn.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_get_history(self):
        conn = _make_conn()
        user = _make_user("client")
        now = datetime.now(timezone.utc)
        conn.fetchrow.return_value = {"id": "quest_1", "client_id": user.id, "assigned_to": None, "status": "open"}
        conn.fetch.return_value = [
            {
                "id": "h1",
                "quest_id": "quest_1",
                "from_status": None,
                "to_status": "draft",
                "changed_by": user.id,
                "changed_by_username": user.username,
                "note": "Quest created",
                "created_at": now,
            },
            {
                "id": "h2",
                "quest_id": "quest_1",
                "from_status": "draft",
                "to_status": "open",
                "changed_by": user.id,
                "changed_by_username": user.username,
                "note": "Quest published to marketplace",
                "created_at": now,
            },
        ]

        result = await quest_service.get_quest_status_history(conn, "quest_1", user)

        assert len(result) == 2
        assert result[0].to_status == QuestStatusEnum.draft
        assert result[1].to_status == QuestStatusEnum.open

    @pytest.mark.asyncio
    async def test_get_history_rejects_non_participant(self):
        conn = _make_conn()
        outsider = _make_user("client", user_id="user_outsider")
        conn.fetchrow.return_value = {
            "id": "quest_1",
            "client_id": "user_client",
            "assigned_to": "user_fl",
            "status": "confirmed",
        }

        with pytest.raises(PermissionError, match="participants or admins"):
            await quest_service.get_quest_status_history(conn, "quest_1", outsider)

    @pytest.mark.asyncio
    async def test_list_quests_hides_drafts_for_anonymous_user_filter(self):
        conn = _make_conn()
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        await quest_service.list_quests(conn, user_id="user_client")

        count_query = conn.fetchval.await_args.args[0]
        fetch_query = conn.fetch.await_args.args[0]
        assert "status <> 'draft'" in count_query
        assert "status <> 'draft'" in fetch_query

    @pytest.mark.asyncio
    async def test_list_quests_allows_owner_drafts_for_personal_filter(self):
        conn = _make_conn()
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []
        user = _make_user("client", user_id="user_client")

        await quest_service.list_quests(conn, user_id=user.id, current_user=user)

        count_query = conn.fetchval.await_args.args[0]
        fetch_query = conn.fetch.await_args.args[0]
        assert "status <> 'draft'" not in count_query
        assert "status <> 'draft'" not in fetch_query


# ---------------------------------------------------------------------------
# apply_to_quest
# ---------------------------------------------------------------------------


class TestApplyToQuest:
    @pytest.mark.asyncio
    async def test_banned_user_cannot_apply(self):
        conn = _make_conn()
        user = _make_user("freelancer", "user_fl", is_banned=True)
        data = QuestApplicationCreate(
            cover_letter="I am very interested in this project and have great skills.",
            proposed_price=4000,
        )

        with pytest.raises(PermissionError, match="Banned users"):
            await quest_service.apply_to_quest(conn, "quest_1", data, user)

    @pytest.mark.asyncio
    async def test_quest_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None
        user = _make_user("freelancer", "user_fl")
        data = QuestApplicationCreate(
            cover_letter="I am very interested in this project and have great skills.",
            proposed_price=4000,
        )

        with pytest.raises(ValueError, match="not found"):
            await quest_service.apply_to_quest(conn, "bad_id", data, user)

    @pytest.mark.asyncio
    async def test_cannot_apply_own_quest(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(client_id="user_fl")
        user = _make_user("freelancer", "user_fl")
        data = QuestApplicationCreate(
            cover_letter="I am very interested in this project and have great skills.",
            proposed_price=4000,
        )

        with pytest.raises(ValueError, match="own quest"):
            await quest_service.apply_to_quest(conn, "quest_1", data, user)

    @pytest.mark.asyncio
    async def test_cannot_apply_closed_quest(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="in_progress")
        user = _make_user("freelancer", "user_fl")
        data = QuestApplicationCreate(
            cover_letter="I am very interested in this project and have great skills.",
            proposed_price=4000,
        )

        with pytest.raises(ValueError, match="status"):
            await quest_service.apply_to_quest(conn, "quest_1", data, user)


# ---------------------------------------------------------------------------
# assign_freelancer
# ---------------------------------------------------------------------------


class TestAssignFreelancer:
    @pytest.mark.asyncio
    async def test_not_client_raises_permission(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(client_id="other_client")
        user = _make_user("client", "user_client")

        with pytest.raises(PermissionError, match="Only client"):
            await quest_service.assign_freelancer(conn, "quest_1", "user_fl", user)

    @pytest.mark.asyncio
    async def test_quest_not_open(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="completed")
        user = _make_user("client")

        with pytest.raises(ValueError, match="status"):
            await quest_service.assign_freelancer(conn, "quest_1", "user_fl", user)

    @pytest.mark.asyncio
    async def test_banned_freelancer_cannot_be_assigned(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(status="open"),
            {"id": "app_1"},
            {"username": "test_fl", "character_class": None, "is_banned": True},
        ]
        conn.fetchval.return_value = 0
        user = _make_user("client")

        with pytest.raises(PermissionError, match="Banned users"):
            await quest_service.assign_freelancer(conn, "quest_1", "user_fl", user)

    @pytest.mark.asyncio
    async def test_assign_success_sets_assigned_status(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(status="open"),
            {"id": "app_1"},
            {"username": "test_fl", "character_class": None, "is_banned": False},
            # R-04: freelancer class row for slot check
            None,  # reset_consecutive_if_stale: no class progress row
            {"id": "w1", "balance": 10000.0},  # hold(): client wallet lookup
            _quest_row(status="assigned", assigned_to="user_fl"),
        ]
        conn.fetchval.return_value = 0  # R-04: active quest count
        conn.fetch.return_value = []
        user = _make_user("client")

        result = await quest_service.assign_freelancer(conn, "quest_1", "user_fl", user)

        assert result.status == QuestStatusEnum.assigned
        assert result.assigned_to == "user_fl"


# ---------------------------------------------------------------------------
# start_quest
# ---------------------------------------------------------------------------


class TestStartQuest:
    @pytest.mark.asyncio
    async def test_banned_user_cannot_start(self):
        conn = _make_conn()
        user = _make_user("freelancer", "user_fl", is_banned=True)

        with pytest.raises(PermissionError, match="Banned users"):
            await quest_service.start_quest(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_not_assigned_freelancer(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="assigned", assigned_to="other_user")
        user = _make_user("freelancer", "user_fl")

        with pytest.raises(PermissionError, match="assigned freelancer"):
            await quest_service.start_quest(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_quest_not_assigned(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="open")
        user = _make_user("freelancer", "user_fl")

        with pytest.raises(ValueError, match="assigned"):
            await quest_service.start_quest(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_start_success_sets_in_progress(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(status="assigned", assigned_to="user_fl"),
            _quest_row(status="in_progress", assigned_to="user_fl"),
        ]
        conn.fetch.return_value = []
        user = _make_user("freelancer", "user_fl")

        result = await quest_service.start_quest(conn, "quest_1", user)

        assert result.status == QuestStatusEnum.in_progress
        assert result.assigned_to == "user_fl"


# ---------------------------------------------------------------------------
# mark_quest_complete
# ---------------------------------------------------------------------------


class TestMarkQuestComplete:
    @pytest.mark.asyncio
    async def test_banned_user_cannot_complete(self):
        conn = _make_conn()
        user = _make_user("freelancer", "user_fl", is_banned=True)

        with pytest.raises(PermissionError, match="Banned users"):
            await quest_service.mark_quest_complete(conn, "quest_1", None, user)

    @pytest.mark.asyncio
    async def test_not_assigned_freelancer(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(
            status="in_progress", assigned_to="other_user"
        )
        user = _make_user("freelancer", "user_fl")

        with pytest.raises(PermissionError, match="assigned"):
            await quest_service.mark_quest_complete(conn, "quest_1", None, user)

    @pytest.mark.asyncio
    async def test_quest_not_in_progress(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="open")
        user = _make_user("freelancer", "user_fl")

        with pytest.raises(ValueError, match="in progress or requested for revision"):
            await quest_service.mark_quest_complete(conn, "quest_1", None, user)

    @pytest.mark.asyncio
    async def test_can_resubmit_after_revision_requested(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(status="revision_requested", assigned_to="user_fl")
            | {
                "revision_reason": "Нужно добавить инструкцию по запуску и поправить README.",
                "revision_requested_at": datetime.now(timezone.utc),
            },
            _quest_row(status="completed", assigned_to="user_fl"),
        ]
        conn.fetch.return_value = []
        user = _make_user("freelancer", "user_fl")
        payload = QuestCompletionCreate(
            delivery_note="README обновлён, инструкция по запуску добавлена.",
        )

        quest, xp_reward = await quest_service.mark_quest_complete(conn, "quest_1", payload, user)

        assert quest.status == QuestStatusEnum.completed
        assert quest.revision_reason is None
        assert xp_reward == 50

    @pytest.mark.asyncio
    async def test_saves_delivery_payload(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(status="in_progress", assigned_to="user_fl"),
            _quest_row(
                status="completed",
                assigned_to="user_fl",
            ) | {
                "delivery_note": "Архив, README и финальные правки приложены.",
                "delivery_url": "https://example.com/result.zip",
                "delivery_submitted_at": datetime.now(timezone.utc),
            },
        ]
        conn.fetch.return_value = []
        user = _make_user("freelancer", "user_fl")
        payload = QuestCompletionCreate(
            delivery_note="Архив, README и финальные правки приложены.",
            delivery_url="https://example.com/result.zip",
        )

        quest, xp_reward = await quest_service.mark_quest_complete(conn, "quest_1", payload, user)

        assert quest.status == QuestStatusEnum.completed
        assert quest.delivery_note == "Архив, README и финальные правки приложены."
        assert quest.delivery_url == "https://example.com/result.zip"
        assert xp_reward == 50


# ---------------------------------------------------------------------------
# cancel_quest
# ---------------------------------------------------------------------------


class TestCancelQuest:
    @pytest.mark.asyncio
    async def test_not_client_raises_permission(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(client_id="other")
        user = _make_user("client")

        with pytest.raises(PermissionError, match="client"):
            await quest_service.cancel_quest(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_cannot_cancel_completed(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="completed")
        user = _make_user("client")

        with pytest.raises(ValueError, match="status"):
            await quest_service.cancel_quest(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_cancel_success(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(status="open"),  # quest lookup
            None,                        # refund_hold: no active hold
        ]
        user = _make_user("client")

        result = await quest_service.cancel_quest(conn, "quest_1", user)
        assert "cancelled" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_cancel_in_progress_not_allowed(self):
        """P1-01: Client unilateral cancellation griefing fix.
        Cancelling an in-progress quest must raise ValueError.
        """
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(status="in_progress", assigned_to="user_fl"),  # quest
            _user_row(user_id="user_fl", xp=50, grade="novice"),      # freelancer
        ]
        user = _make_user("client")

        with pytest.raises(ValueError, match="Cannot unilaterally cancel"):
            await quest_service.cancel_quest(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_cancel_quest_in_revision_requested_succeeds(self):
        """P1-2 FIX: A quest under revision CAN be cancelled by the client."""
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(
                status=QuestStatusEnum.revision_requested.value,
                assigned_to="freelancer-uuid",
            ),
            None,  # refund_hold: no active escrow hold
        ]
        user = _make_user("client")

        result = await quest_service.cancel_quest(conn, "quest_1", user)
        assert "cancelled" in result["message"].lower()


# ---------------------------------------------------------------------------
# confirm_quest_completion — the critical atomic operation
# ---------------------------------------------------------------------------


class TestConfirmQuestCompletion:
    @pytest.mark.asyncio
    async def test_not_client_raises_permission(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(
            status="completed", client_id="other_client", assigned_to="user_fl"
        )
        user = _make_user("client")

        with pytest.raises(PermissionError, match="Only client"):
            await quest_service.confirm_quest_completion(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_quest_not_completed(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="in_progress")
        user = _make_user("client")

        with pytest.raises(ValueError, match="not been marked"):
            await quest_service.confirm_quest_completion(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_confirm_runs_in_transaction(self):
        """Verify that confirm uses conn.transaction() for atomicity and returns fee info."""
        from app.models.badge_notification import BadgeAwardResult
        conn = _make_conn()

        quest = _quest_row(status="completed", assigned_to="user_fl")
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice")

        # fetchrow calls: quest + freelancer + chain_step(None) + final updated_quest
        conn.fetchrow.side_effect = [quest, freelancer, None, quest]
        # fetchval: CAS update RETURNING id, badge count
        conn.fetchval.side_effect = ["quest_1", 5]

        class _FakeTransaction:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False

        conn.transaction = MagicMock(return_value=_FakeTransaction())

        user = _make_user("client")
        with patch("app.services.quest_service.class_service") as mock_cls, \
             patch("app.services.quest_service.badge_service") as mock_badge, \
             patch("app.services.quest_service.wallet_service.split_payment", new=AsyncMock(return_value={
                 "gross_amount": Decimal("100.00"),
                 "fee_percent": Decimal("10.00"),
                 "freelancer_amount": Decimal("90.00"),
                 "platform_fee": Decimal("10.00"),
                 "client_balance": Decimal("0.00"),
                 "freelancer_balance": Decimal("90.00"),
                 "platform_balance": Decimal("10.00"),
             })), \
             patch("app.services.quest_service.guild_economy_service.apply_quest_completion_rewards", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.guild_economy_service.award_solo_artifact_drop", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.trust_score_service.refresh_trust_score", new=AsyncMock()), \
             patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()), \
             patch("app.services.quest_service.message_service.create_system_message", new=AsyncMock()):
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={})
            mock_cls.add_class_xp = AsyncMock(return_value={"class_xp_gained": 0, "class_level_up": False})
            mock_cls.reset_consecutive_if_stale = AsyncMock()
            mock_badge.check_and_award = AsyncMock(return_value=BadgeAwardResult(newly_earned=[]))
            result = await quest_service.confirm_quest_completion(conn, "quest_1", user)

        # Verify transaction() was called at least once (money TX + post-commit notification TX)
        assert conn.transaction.call_count >= 2

        assert "confirmed" in result["message"].lower() or "reward" in result["message"].lower()
        assert result["xp_reward"] > 0
        assert "platform_fee" in result
        assert "fee_percent" in result
        assert "stat_delta" in result
        assert result["stat_delta"]["int"] >= 0

    @pytest.mark.asyncio
    async def test_confirm_surfaces_actionable_no_hold_message(self):
        conn = _make_conn()
        quest = _quest_row(status="completed", assigned_to="user_fl")
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice")

        conn.fetchrow.side_effect = [quest, freelancer]
        conn.fetchval.side_effect = ["quest_1"]

        user = _make_user("client")
        with patch("app.services.quest_service.class_service") as mock_cls:
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={})
            with patch(
                "app.services.quest_service.wallet_service.split_payment",
                new=AsyncMock(side_effect=quest_service.wallet_service.InsufficientFundsError("Insufficient funds")),
            ):
                with pytest.raises(
                    quest_service.wallet_service.InsufficientFundsError,
                    match="active escrow hold or enough client balance",
                ):
                    await quest_service.confirm_quest_completion(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_confirm_surfaces_escrow_amount_mismatch(self):
        conn = _make_conn()
        quest = _quest_row(status="completed", assigned_to="user_fl")
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice")

        conn.fetchrow.side_effect = [quest, freelancer]
        conn.fetchval.side_effect = ["quest_1"]

        user = _make_user("client")
        with patch("app.services.quest_service.class_service") as mock_cls:
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={})
            with patch(
                "app.services.quest_service.wallet_service.split_payment",
                new=AsyncMock(side_effect=ValueError("Escrow hold amount does not match payout amount")),
            ):
                with pytest.raises(ValueError, match="Escrow hold amount does not match payout amount"):
                    await quest_service.confirm_quest_completion(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_confirm_uses_existing_hold_before_direct_debit(self):
        from app.models.badge_notification import BadgeAwardResult

        conn = _make_conn()
        quest = _quest_row(status="completed", assigned_to="user_fl")
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice")

        conn.fetchrow.side_effect = [quest, freelancer, None, quest]
        conn.fetchval.side_effect = ["quest_1", 5]

        user = _make_user("client")
        with patch("app.services.quest_service.class_service") as mock_cls, \
             patch("app.services.quest_service.badge_service") as mock_badge, \
             patch("app.services.quest_service.wallet_service.split_payment", new=AsyncMock(return_value={
                 "gross_amount": Decimal("100.00"),
                 "fee_percent": Decimal("10.00"),
                 "freelancer_amount": Decimal("90.00"),
                 "platform_fee": Decimal("10.00"),
                 "client_balance": Decimal("0.00"),
                 "freelancer_balance": Decimal("90.00"),
                 "platform_balance": Decimal("10.00"),
             })) as mock_split, \
             patch("app.services.quest_service.guild_economy_service.apply_quest_completion_rewards", new=AsyncMock(return_value={
                 "guild_id": "guild_1",
                 "guild_name": "Crimson Forge",
                 "treasury_delta": Decimal("3.50"),
                 "guild_tokens_delta": 1,
                 "contribution_delta": 125,
                 "card_drop": None,
             })), \
             patch("app.services.quest_service.trust_score_service.refresh_trust_score", new=AsyncMock()), \
             patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()), \
             patch("app.services.quest_service.message_service.create_system_message", new=AsyncMock()):
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={})
            mock_cls.add_class_xp = AsyncMock(return_value={"class_xp_gained": 0, "class_level_up": False})
            mock_cls.reset_consecutive_if_stale = AsyncMock()
            mock_badge.check_and_award = AsyncMock(return_value=BadgeAwardResult(newly_earned=[]))
            result = await quest_service.confirm_quest_completion(conn, "quest_1", user)

        mock_split.assert_awaited_once()
        assert result["money_reward"] == Decimal("90.00")
        assert result["guild_economy"]["guild_id"] == "guild_1"

    @pytest.mark.asyncio
    async def test_confirm_invokes_guild_economy_once_with_expected_payload(self):
        from app.models.badge_notification import BadgeAwardResult

        conn = _make_conn()
        quest = _quest_row(status="completed", assigned_to="user_fl", budget=Decimal("10000"), xp_reward=500)
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice")

        conn.fetchrow.side_effect = [quest, freelancer, None, quest]
        conn.fetchval.side_effect = ["quest_1", 5]

        user = _make_user("client")
        with patch("app.services.quest_service.class_service") as mock_cls, \
             patch("app.services.quest_service.badge_service") as mock_badge, \
             patch("app.services.quest_service.wallet_service.split_payment", new=AsyncMock(return_value={
                 "gross_amount": Decimal("10000.00"),
                 "fee_percent": Decimal("10.00"),
                 "freelancer_amount": Decimal("9000.00"),
                 "platform_fee": Decimal("1000.00"),
                 "client_balance": Decimal("0.00"),
                 "freelancer_balance": Decimal("9000.00"),
                 "platform_balance": Decimal("10000.00"),
             })), \
             patch("app.services.quest_service.guild_economy_service.apply_quest_completion_rewards", new=AsyncMock(return_value={
                 "guild_id": "guild_1",
                 "guild_name": "Crimson Forge",
                 "treasury_delta": Decimal("3.50"),
                 "guild_tokens_delta": 1,
                 "contribution_delta": 125,
                 "card_drop": None,
             })) as mock_guild_rewards, \
             patch("app.services.quest_service.trust_score_service.refresh_trust_score", new=AsyncMock()), \
             patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()), \
             patch("app.services.quest_service.message_service.create_system_message", new=AsyncMock()):
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={})
            mock_cls.add_class_xp = AsyncMock(return_value={"class_xp_gained": 0, "class_level_up": False})
            mock_cls.reset_consecutive_if_stale = AsyncMock()
            mock_badge.check_and_award = AsyncMock(return_value=BadgeAwardResult(newly_earned=[]))
            result = await quest_service.confirm_quest_completion(conn, "quest_1", user)

        mock_guild_rewards.assert_awaited_once()
        _, guild_kwargs = mock_guild_rewards.await_args
        assert guild_kwargs["quest_id"] == "quest_1"
        assert guild_kwargs["freelancer_id"] == "user_fl"
        assert guild_kwargs["gross_amount"] == 10000.0
        assert guild_kwargs["platform_fee"] == Decimal("1000.00")
        assert guild_kwargs["xp_reward"] == 500
        assert guild_kwargs["source"] == "client_confirm"
        assert result["xp_reward"] == 500
        assert result["guild_economy"]["guild_id"] == "guild_1"

    @pytest.mark.asyncio
    async def test_confirm_applies_deadline_penalty_without_ability(self):
        from app.models.badge_notification import BadgeAwardResult

        conn = _make_conn()
        late_deadline = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        late_delivery = datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc)
        quest = _quest_row(status="completed", assigned_to="user_fl", budget=Decimal("10000"), xp_reward=100)
        quest["deadline"] = late_deadline
        quest["delivery_submitted_at"] = late_delivery
        quest["completed_at"] = late_delivery
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice")

        conn.fetchrow.side_effect = [quest, freelancer, None, quest]
        conn.fetchval.side_effect = ["quest_1", 5]
        user = _make_user("client")

        with patch("app.services.quest_service.class_service") as mock_cls, \
             patch("app.services.quest_service.badge_service") as mock_badge, \
             patch("app.services.quest_service.wallet_service.split_payment", new=AsyncMock(return_value={
                 "freelancer_amount": Decimal("9000.00"),
                 "platform_fee": Decimal("1000.00"),
                 "fee_percent": Decimal("10.00"),
                 "client_surcharge_amount": Decimal("0.00"),
             })), \
             patch("app.services.quest_service.guild_economy_service.apply_quest_completion_rewards", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.guild_economy_service.award_solo_artifact_drop", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.trust_score_service.refresh_trust_score", new=AsyncMock()), \
             patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()), \
             patch("app.services.quest_service.message_service.create_system_message", new=AsyncMock()):
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={})
            mock_cls.add_class_xp = AsyncMock(return_value={"class_xp_gained": 0, "class_level_up": False})
            mock_badge.check_and_award = AsyncMock(return_value=BadgeAwardResult(newly_earned=[]))
            result = await quest_service.confirm_quest_completion(conn, "quest_1", user)

        assert result["xp_reward"] == 80
        assert result["deadline_penalty_rate"] == pytest.approx(0.20)

    @pytest.mark.asyncio
    async def test_confirm_reduces_deadline_penalty_with_alchemist_ability(self):
        from app.models.badge_notification import BadgeAwardResult

        conn = _make_conn()
        late_deadline = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        late_delivery = datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc)
        quest = _quest_row(status="completed", assigned_to="user_fl", budget=Decimal("10000"), xp_reward=100)
        quest["deadline"] = late_deadline
        quest["delivery_submitted_at"] = late_delivery
        quest["completed_at"] = late_delivery
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice", character_class="alchemist")

        conn.fetchrow.side_effect = [quest, freelancer, None, quest]
        conn.fetchval.side_effect = ["quest_1", 5]
        user = _make_user("client")

        with patch("app.services.quest_service.class_service") as mock_cls, \
             patch("app.services.quest_service.badge_service") as mock_badge, \
             patch("app.services.quest_service.wallet_service.split_payment", new=AsyncMock(return_value={
                 "freelancer_amount": Decimal("9000.00"),
                 "platform_fee": Decimal("1000.00"),
                 "fee_percent": Decimal("10.00"),
                 "client_surcharge_amount": Decimal("0.00"),
             })), \
             patch("app.services.quest_service.guild_economy_service.apply_quest_completion_rewards", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.guild_economy_service.award_solo_artifact_drop", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.trust_score_service.refresh_trust_score", new=AsyncMock()), \
             patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()), \
             patch("app.services.quest_service.message_service.create_system_message", new=AsyncMock()):
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={"deadline_penalty_reduce": 0.10})
            mock_cls.add_class_xp = AsyncMock(return_value={"class_xp_gained": 0, "class_level_up": False})
            mock_badge.check_and_award = AsyncMock(return_value=BadgeAwardResult(newly_earned=[]))
            result = await quest_service.confirm_quest_completion(conn, "quest_1", user)

        assert result["xp_reward"] == 82
        assert result["deadline_penalty_rate"] == pytest.approx(0.18)

    @pytest.mark.asyncio
    async def test_confirm_applies_urgent_payout_bonus_as_client_surcharge(self):
        from app.models.badge_notification import BadgeAwardResult

        conn = _make_conn()
        quest = _quest_row(status="completed", assigned_to="user_fl", budget=Decimal("100.00"), xp_reward=100)
        quest["is_urgent"] = True
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice", character_class="rogue")

        conn.fetchrow.side_effect = [quest, freelancer, None, quest]
        conn.fetchval.side_effect = ["quest_1", 5]
        user = _make_user("client")

        with patch("app.services.quest_service.class_service") as mock_cls, \
             patch("app.services.quest_service.badge_service") as mock_badge, \
             patch("app.services.quest_service.wallet_service.split_payment", new=AsyncMock(return_value={
                 "freelancer_amount": Decimal("100.00"),
                 "platform_fee": Decimal("10.00"),
                 "fee_percent": Decimal("10.00"),
                 "client_surcharge_amount": Decimal("10.00"),
             })) as mock_split, \
             patch("app.services.quest_service.guild_economy_service.apply_quest_completion_rewards", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.guild_economy_service.award_solo_artifact_drop", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.trust_score_service.refresh_trust_score", new=AsyncMock()), \
             patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()), \
             patch("app.services.quest_service.message_service.create_system_message", new=AsyncMock()):
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={"urgent_payout_bonus": 0.10})
            mock_cls.add_class_xp = AsyncMock(return_value={"class_xp_gained": 0, "class_level_up": False})
            mock_badge.check_and_award = AsyncMock(return_value=BadgeAwardResult(newly_earned=[]))
            result = await quest_service.confirm_quest_completion(conn, "quest_1", user)

        _, split_kwargs = mock_split.await_args
        assert split_kwargs["client_surcharge_amount"] == Decimal("10.00")
        assert result["money_reward"] == Decimal("100.00")
        assert result["client_surcharge_amount"] == Decimal("10.00")

    @pytest.mark.asyncio
    async def test_confirm_refreshes_trust_score_for_assigned_freelancer(self):
        from app.models.badge_notification import BadgeAwardResult

        conn = _make_conn()
        quest = _quest_row(status="completed", assigned_to="user_fl", budget=Decimal("100.00"), xp_reward=50)
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice")

        conn.fetchrow.side_effect = [quest, freelancer, None, quest]
        conn.fetchval.side_effect = ["quest_1", 5]
        user = _make_user("client")

        with patch("app.services.quest_service.class_service") as mock_cls, \
             patch("app.services.quest_service.badge_service") as mock_badge, \
             patch("app.services.quest_service.wallet_service.split_payment", new=AsyncMock(return_value={
                 "freelancer_amount": Decimal("90.00"),
                 "platform_fee": Decimal("10.00"),
                 "fee_percent": Decimal("10.00"),
                 "client_surcharge_amount": Decimal("0.00"),
             })), \
             patch("app.services.quest_service.guild_economy_service.apply_quest_completion_rewards", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.guild_economy_service.award_solo_artifact_drop", new=AsyncMock(return_value=None)), \
             patch("app.services.quest_service.trust_score_service.refresh_trust_score", new=AsyncMock()) as mock_refresh_trust, \
             patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()), \
             patch("app.services.quest_service.message_service.create_system_message", new=AsyncMock()):
            mock_cls.check_burnout = AsyncMock(return_value=False)
            mock_cls.get_active_ability_effects = AsyncMock(return_value={})
            mock_cls.add_class_xp = AsyncMock(return_value={"class_xp_gained": 0, "class_level_up": False})
            mock_cls.reset_consecutive_if_stale = AsyncMock()
            mock_badge.check_and_award = AsyncMock(return_value=BadgeAwardResult(newly_earned=[]))
            await quest_service.confirm_quest_completion(conn, "quest_1", user)

        mock_refresh_trust.assert_awaited_once_with(conn, "user_fl")


# ---------------------------------------------------------------------------
# request_quest_revision
# ---------------------------------------------------------------------------


class TestRequestQuestRevision:
    @pytest.mark.asyncio
    async def test_not_client_raises_permission(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(
            status="completed", client_id="other_client", assigned_to="user_fl"
        )
        user = _make_user("client")
        payload = QuestRevisionRequest(
            revision_reason="Нужно дополнить инструкцию по запуску и обновить README.",
        )

        with pytest.raises(PermissionError, match="Only client"):
            await quest_service.request_quest_revision(conn, "quest_1", payload, user)

    @pytest.mark.asyncio
    async def test_quest_not_completed(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="in_progress")
        user = _make_user("client")
        payload = QuestRevisionRequest(
            revision_reason="Нужно дополнить инструкцию по запуску и обновить README.",
        )

        with pytest.raises(ValueError, match="completed quest"):
            await quest_service.request_quest_revision(conn, "quest_1", payload, user)

    @pytest.mark.asyncio
    async def test_request_success_sets_revision_requested_status(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(status="completed", assigned_to="user_fl"),
            _quest_row(status="revision_requested", assigned_to="user_fl")
            | {
                "revision_reason": "Добавьте инструкцию по деплою и поправьте README.",
                "revision_requested_at": datetime.now(timezone.utc),
            },
        ]
        conn.fetch.return_value = []
        user = _make_user("client")
        payload = QuestRevisionRequest(
            revision_reason="Добавьте инструкцию по деплою и поправьте README.",
        )

        result = await quest_service.request_quest_revision(conn, "quest_1", payload, user)

        assert result.status == QuestStatusEnum.revision_requested
        assert result.revision_reason == "Добавьте инструкцию по деплою и поправьте README."


# ---------------------------------------------------------------------------
# get_quest_applications
# ---------------------------------------------------------------------------


class TestGetQuestApplications:
    @pytest.mark.asyncio
    async def test_not_client_raises_permission(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(client_id="other")
        user = _make_user("client")

        with pytest.raises(PermissionError, match="client"):
            await quest_service.get_quest_applications(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row()
        conn.fetch.return_value = []
        user = _make_user("client")

        result = await quest_service.get_quest_applications(conn, "quest_1", user)
        assert result["applications"] == []
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# Training Quest — calculate_training_xp_reward
# ---------------------------------------------------------------------------


class TestCalculateTrainingXpReward:
    def test_base_xp_clamped_to_min(self):
        from app.core.rewards import calculate_training_xp_reward
        result = calculate_training_xp_reward(1, GradeEnum.novice, GradeEnum.novice)
        assert result == 5  # TRAINING_MIN_XP

    def test_base_xp_clamped_to_max(self):
        from app.core.rewards import calculate_training_xp_reward
        result = calculate_training_xp_reward(999, GradeEnum.novice, GradeEnum.novice)
        assert result == 150  # TRAINING_MAX_XP

    def test_equal_grade_no_bonus(self):
        from app.core.rewards import calculate_training_xp_reward
        result = calculate_training_xp_reward(100, GradeEnum.junior, GradeEnum.junior)
        assert result == 100  # no bonus

    def test_higher_quest_grade_applies_complexity_bonus(self):
        from app.core.rewards import calculate_training_xp_reward
        # senior quest vs novice user: 100 * 1.5 = 150 (capped)
        result = calculate_training_xp_reward(100, GradeEnum.senior, GradeEnum.novice)
        assert result == 150

    def test_complexity_bonus_does_not_exceed_cap(self):
        from app.core.rewards import calculate_training_xp_reward
        # 120 * 1.5 = 180, clamped to 150
        result = calculate_training_xp_reward(120, GradeEnum.middle, GradeEnum.novice)
        assert result == 150

    def test_lower_quest_grade_no_bonus(self):
        from app.core.rewards import calculate_training_xp_reward
        result = calculate_training_xp_reward(80, GradeEnum.novice, GradeEnum.senior)
        assert result == 80


# ---------------------------------------------------------------------------
# Training Quest — list_training_quests
# ---------------------------------------------------------------------------


class TestListTrainingQuests:
    @pytest.mark.asyncio
    async def test_empty_list(self):
        conn = _make_conn()
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        result = await quest_service.list_training_quests(conn, page=1, page_size=10)
        assert result.quests == []
        assert result.total == 0
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_returns_training_quests(self):
        conn = _make_conn()
        row = _quest_row(quest_id="t1", status="open")
        row["quest_type"] = "training"
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [row]

        result = await quest_service.list_training_quests(conn, page=1, page_size=10)
        assert len(result.quests) == 1
        assert result.quests[0].id == "t1"
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_grade_filter_passes_arg(self):
        conn = _make_conn()
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        await quest_service.list_training_quests(
            conn, page=1, page_size=10, grade_filter=GradeEnum.junior
        )
        # Verify the grade value was passed in args
        fetch_call = conn.fetch.call_args
        assert "junior" in fetch_call.args


# ---------------------------------------------------------------------------
# Training Quest — create_training_quest
# ---------------------------------------------------------------------------


class TestCreateTrainingQuest:
    @pytest.mark.asyncio
    async def test_non_admin_raises_permission(self):
        from app.models.quest import TrainingQuestCreate
        conn = _make_conn()
        user = _make_user("freelancer", user_id="fl1")
        data = TrainingQuestCreate(
            title="Test Training",
            description="Тренировочный квест для тестирования создания",
            required_grade=GradeEnum.novice,
            skills=["python"],
            xp_reward=50,
        )
        with pytest.raises(PermissionError, match="admin"):
            await quest_service.create_training_quest(conn, data, user)

    @pytest.mark.asyncio
    async def test_admin_creates_training_quest(self):
        from app.models.quest import TrainingQuestCreate
        conn = _make_conn()
        user = _make_user("admin", user_id="admin1")
        data = TrainingQuestCreate(
            title="Python Basics",
            description="Изучите основы Python и напишите скрипт обработки данных",
            required_grade=GradeEnum.novice,
            skills=["python"],
            xp_reward=80,
        )

        result = await quest_service.create_training_quest(conn, data, user)

        assert result.quest_type == "training"
        assert result.client_id == "system"
        assert result.client_username == "Гильдия Мастеров"
        assert result.budget == Decimal("0")
        assert result.xp_reward == 80  # novice quest / novice base → no bonus
        assert result.status == "open"
        assert result.title == "Python Basics"
        # Verify INSERT was called
        conn.execute.assert_awaited()


# ---------------------------------------------------------------------------
# Training Quest — accept_training_quest
# ---------------------------------------------------------------------------


class TestAcceptTrainingQuest:
    def _training_row(self, **overrides):
        row = _quest_row(quest_id="tq_1", status="open", budget=Decimal("0"), xp_reward=50)
        row["quest_type"] = "training"
        row["required_grade"] = "novice"
        row.update(overrides)
        return row

    @pytest.mark.asyncio
    async def test_banned_user_rejected(self):
        conn = _make_conn()
        user = _make_user("freelancer", user_id="fl1", is_banned=True)

        with pytest.raises(PermissionError, match="Banned"):
            await quest_service.accept_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_quest_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not found"):
            await quest_service.accept_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_not_training_quest_rejected(self):
        conn = _make_conn()
        row = _quest_row(status="open")
        row["quest_type"] = "standard"
        conn.fetchrow.return_value = row
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not a training"):
            await quest_service.accept_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_quest_not_open_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = self._training_row(status="in_progress")
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not available"):
            await quest_service.accept_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_grade_too_low_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = self._training_row(required_grade="senior")
        user = _make_user("freelancer", user_id="fl1", grade=GradeEnum.novice)

        with pytest.raises(ValueError, match="grade"):
            await quest_service.accept_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_daily_cap_reached_rejected(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [self._training_row()]
        # _get_training_xp_earned_today → 500 (at cap)
        conn.fetchval.return_value = 500
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="cap reached"):
            await quest_service.accept_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_successful_accept(self):
        conn = _make_conn()
        accepted_row = self._training_row(status="in_progress", assigned_to="fl1")
        conn.fetchrow.side_effect = [self._training_row(), accepted_row]
        conn.fetchval.return_value = 0  # earned today = 0
        user = _make_user("freelancer", user_id="fl1")

        result = await quest_service.accept_training_quest(conn, "tq_1", user)

        assert result.status == "in_progress"
        assert result.assigned_to == "fl1"
        conn.execute.assert_awaited()


# ---------------------------------------------------------------------------
# Training Quest — complete_training_quest
# ---------------------------------------------------------------------------


class TestCompleteTrainingQuest:
    def _training_row(self, **overrides):
        row = _quest_row(
            quest_id="tq_1", status="in_progress", assigned_to="fl1",
            budget=Decimal("0"), xp_reward=50, required_grade="novice",
        )
        row["quest_type"] = "training"
        row.update(overrides)
        return row

    @pytest.mark.asyncio
    async def test_banned_user_rejected(self):
        conn = _make_conn()
        user = _make_user("freelancer", user_id="fl1", is_banned=True)

        with pytest.raises(PermissionError, match="Banned"):
            await quest_service.complete_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_quest_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not found"):
            await quest_service.complete_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_not_training_quest_rejected(self):
        conn = _make_conn()
        row = _quest_row(status="in_progress", assigned_to="fl1")
        row["quest_type"] = "standard"
        conn.fetchrow.return_value = row
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not a training"):
            await quest_service.complete_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_not_in_progress_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = self._training_row(status="open")
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not in progress"):
            await quest_service.complete_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_wrong_freelancer_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = self._training_row(assigned_to="other_fl")
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(PermissionError, match="assigned freelancer"):
            await quest_service.complete_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_daily_cap_exhausted_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = self._training_row()
        conn.fetchval.return_value = 500  # already at cap
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="cap reached"):
            await quest_service.complete_training_quest(conn, "tq_1", user)

    @pytest.mark.asyncio
    async def test_successful_completion(self):
        from app.models.badge_notification import BadgeAwardResult

        conn = _make_conn()
        freelancer_row = _user_row(user_id="fl1", xp=50, level=1, grade="novice")
        confirmed_row = self._training_row(status="confirmed")
        # fetchrow calls: quest (FOR UPDATE), freelancer (FOR UPDATE), final quest
        conn.fetchrow.side_effect = [self._training_row(), freelancer_row, confirmed_row]
        # fetchval calls: _get_training_xp_earned_today=0, UPDATE RETURNING id, badge count
        conn.fetchval.side_effect = [0, "tq_1", 5]
        user = _make_user("freelancer", user_id="fl1")

        with patch("app.services.quest_service.badge_service") as mock_badge, \
             patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()):
            mock_badge.check_and_award = AsyncMock(
                return_value=BadgeAwardResult(newly_earned=[])
            )
            result = await quest_service.complete_training_quest(conn, "tq_1", user)

        assert result["xp_reward"] == 50
        assert result["daily_xp_earned"] == 50
        assert result["daily_xp_cap"] == 500
        assert result["message"] == "Training quest completed!"
        assert isinstance(result["badges_earned"], list)

    @pytest.mark.asyncio
    async def test_completion_clamps_xp_to_remaining_cap(self):
        from app.models.badge_notification import BadgeAwardResult

        conn = _make_conn()
        freelancer_row = _user_row(user_id="fl1", xp=50, level=1, grade="novice")
        confirmed_row = self._training_row(status="confirmed")
        conn.fetchrow.side_effect = [
            self._training_row(xp_reward=100),  # quest wants to give 100 XP
            freelancer_row,
            confirmed_row,
        ]
        # earned_today=450, remaining=50 → xp clamped to 50 (not 100)
        conn.fetchval.side_effect = [450, "tq_1", 5]
        user = _make_user("freelancer", user_id="fl1")

        with patch("app.services.quest_service.badge_service") as mock_badge, \
             patch("app.services.quest_service.notification_service.create_notification", new=AsyncMock()):
            mock_badge.check_and_award = AsyncMock(
                return_value=BadgeAwardResult(newly_earned=[])
            )
            result = await quest_service.complete_training_quest(conn, "tq_1", user)

        assert result["xp_reward"] == 50  # clamped from 100 to 50
        assert result["daily_xp_earned"] == 500  # 450 + 50


# ---------------------------------------------------------------------------
# Raid quest tests
# ---------------------------------------------------------------------------


def _raid_row(**overrides):
    """Fake asyncpg Record-like dict for a raid quest."""
    row = _quest_row(
        quest_id="raid_1", status="open", budget=Decimal("20000"),
        xp_reward=100, required_grade="novice",
    )
    row["quest_type"] = "raid"
    row["raid_max_members"] = 4
    row["raid_current_members"] = 0
    row.update(overrides)
    return row


def _participant_row(user_id="fl1", role_slot="developer", quest_id="raid_1"):
    from datetime import datetime, timezone
    return {
        "id": f"part_{user_id}",
        "quest_id": quest_id,
        "user_id": user_id,
        "username": f"user_{user_id}",
        "role_slot": role_slot,
        "joined_at": datetime.now(timezone.utc),
    }


class TestListRaidQuests:
    @pytest.mark.asyncio
    async def test_empty_list(self):
        conn = _make_conn()
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        result = await quest_service.list_raid_quests(conn, page=1, page_size=10)
        assert result.quests == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_returns_raid_quests(self):
        conn = _make_conn()
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_raid_row()]

        result = await quest_service.list_raid_quests(conn, page=1, page_size=10)
        assert result.total == 1
        assert len(result.quests) == 1
        assert result.quests[0].quest_type == "raid"


class TestCreateRaidQuest:
    @pytest.mark.asyncio
    async def test_freelancer_rejected(self):
        conn = _make_conn()
        from app.models.quest import RaidQuestCreate
        data = RaidQuestCreate(
            title="Raid quest", description="A co-op raid quest for testing purposes",
            required_grade="novice", skills=["python"], budget=Decimal("5000"),
            xp_reward=50, raid_max_members=4,
        )
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(PermissionError, match="Only clients or admins"):
            await quest_service.create_raid_quest(conn, data, user)

    @pytest.mark.asyncio
    async def test_client_creates_raid(self):
        conn = _make_conn()
        from app.models.quest import RaidQuestCreate
        data = RaidQuestCreate(
            title="Raid quest", description="A co-op raid quest for testing purposes",
            required_grade="novice", skills=["python"], budget=Decimal("5000"),
            xp_reward=50, raid_max_members=4,
        )
        user = _make_user("client", user_id="user_client")

        conn.fetchrow.return_value = _raid_row()
        result = await quest_service.create_raid_quest(conn, data, user)

        assert result.quest_type == "raid"
        assert result.raid_max_members == 4

    @pytest.mark.asyncio
    async def test_role_slots_exceed_max_members_rejected(self):
        conn = _make_conn()
        from app.models.quest import RaidQuestCreate
        data = RaidQuestCreate(
            title="Raid quest", description="A co-op raid quest for testing purposes",
            required_grade="novice", skills=["python"], budget=Decimal("5000"),
            xp_reward=50, raid_max_members=2, role_slots=["leader", "developer", "tester"],
        )
        user = _make_user("client", user_id="user_client")

        with pytest.raises(ValueError, match="role_slots count"):
            await quest_service.create_raid_quest(conn, data, user)


class TestJoinRaidQuest:
    @pytest.mark.asyncio
    async def test_banned_user_rejected(self):
        conn = _make_conn()
        user = _make_user("freelancer", user_id="fl1", is_banned=True)

        with pytest.raises(PermissionError, match="Banned"):
            await quest_service.join_raid_quest(conn, "raid_1", "developer", user)

    @pytest.mark.asyncio
    async def test_quest_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not found"):
            await quest_service.join_raid_quest(conn, "raid_1", "developer", user)

    @pytest.mark.asyncio
    async def test_not_raid_rejected(self):
        conn = _make_conn()
        row = _quest_row()
        row["quest_type"] = "standard"
        row["raid_max_members"] = None
        row["raid_current_members"] = 0
        conn.fetchrow.return_value = row
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not a raid"):
            await quest_service.join_raid_quest(conn, "raid_1", "developer", user)

    @pytest.mark.asyncio
    async def test_party_full_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _raid_row(raid_current_members=4, raid_max_members=4)
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="full"):
            await quest_service.join_raid_quest(conn, "raid_1", "developer", user)

    @pytest.mark.asyncio
    async def test_duplicate_join_rejected(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _raid_row(raid_current_members=1),  # quest
            {"id": "existing_part"},             # existing participant
        ]
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="already joined"):
            await quest_service.join_raid_quest(conn, "raid_1", "developer", user)

    @pytest.mark.asyncio
    async def test_role_slot_conflict_rejected(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _raid_row(raid_current_members=1),  # quest
            None,                                # no existing participant for this user
            {"id": "taken_role"},                 # role already taken
        ]
        user = _make_user("freelancer", user_id="fl2")

        with pytest.raises(ValueError, match="already taken"):
            await quest_service.join_raid_quest(conn, "raid_1", "developer", user)

    @pytest.mark.asyncio
    async def test_grade_too_low_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _raid_row(required_grade="middle")
        user = _make_user("freelancer", user_id="fl1", grade=GradeEnum.novice)

        with pytest.raises(ValueError, match="grade"):
            await quest_service.join_raid_quest(conn, "raid_1", "developer", user)

    @pytest.mark.asyncio
    async def test_successful_join(self):
        conn = _make_conn()
        # fetchrow calls: quest (FOR UPDATE), duplicate check, role check
        conn.fetchrow.side_effect = [
            _raid_row(raid_current_members=1),  # quest
            None,                                 # no duplicate
            None,                                 # role not taken
        ]
        user = _make_user("freelancer", user_id="fl2")

        # get_raid_party after join: quest + participants
        party_quest = _raid_row(raid_current_members=2)
        conn.fetchrow.side_effect = [
            _raid_row(raid_current_members=1), None, None,  # join flow
            party_quest,  # get_raid_party quest read
        ]
        conn.fetch.return_value = [_participant_row("fl1"), _participant_row("fl2", "tester")]

        result = await quest_service.join_raid_quest(conn, "raid_1", "developer", user)
        assert result.current_members == 2


class TestLeaveRaidQuest:
    @pytest.mark.asyncio
    async def test_quest_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not found"):
            await quest_service.leave_raid_quest(conn, "raid_1", user)

    @pytest.mark.asyncio
    async def test_not_a_member_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _raid_row(raid_current_members=1)
        conn.fetchval.return_value = None  # DELETE returns nothing
        user = _make_user("freelancer", user_id="fl_outsider")

        with pytest.raises(ValueError, match="not a member"):
            await quest_service.leave_raid_quest(conn, "raid_1", user)

    @pytest.mark.asyncio
    async def test_already_started_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _raid_row(status="in_progress")
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="already started"):
            await quest_service.leave_raid_quest(conn, "raid_1", user)

    @pytest.mark.asyncio
    async def test_successful_leave(self):
        conn = _make_conn()
        quest = _raid_row(raid_current_members=2)
        conn.fetchrow.side_effect = [
            quest,                                # leave: quest row
            _raid_row(raid_current_members=1),    # get_raid_party: quest read
        ]
        conn.fetchval.return_value = "part_fl1"  # DELETE RETURNING id
        conn.fetch.return_value = [_participant_row("fl2", "tester")]  # remaining
        user = _make_user("freelancer", user_id="fl1")

        result = await quest_service.leave_raid_quest(conn, "raid_1", user)
        assert result.current_members == 1


class TestStartRaidQuest:
    @pytest.mark.asyncio
    async def test_quest_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None
        user = _make_user("client")

        with pytest.raises(ValueError, match="not found"):
            await quest_service.start_raid_quest(conn, "raid_1", user)

    @pytest.mark.asyncio
    async def test_not_owner_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _raid_row(client_id="other_client")
        user = _make_user("client", user_id="user_client")

        with pytest.raises(PermissionError, match="owner or admin"):
            await quest_service.start_raid_quest(conn, "raid_1", user)

    @pytest.mark.asyncio
    async def test_not_enough_members_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _raid_row(raid_current_members=1)
        user = _make_user("client")

        with pytest.raises(ValueError, match="at least"):
            await quest_service.start_raid_quest(conn, "raid_1", user)

    @pytest.mark.asyncio
    async def test_successful_start(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _raid_row(raid_current_members=3),                 # start: quest FOR UPDATE
            _raid_row(status="in_progress", raid_current_members=3),  # final read
        ]
        user = _make_user("client")

        result = await quest_service.start_raid_quest(conn, "raid_1", user)
        assert result.status == "in_progress"


class TestCompleteRaidQuest:
    @pytest.mark.asyncio
    async def test_quest_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not found"):
            await quest_service.complete_raid_quest(conn, "raid_1", user)

    @pytest.mark.asyncio
    async def test_not_in_progress_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _raid_row(status="open")
        user = _make_user("freelancer", user_id="fl1")

        with pytest.raises(ValueError, match="not in progress"):
            await quest_service.complete_raid_quest(conn, "raid_1", user)

    @pytest.mark.asyncio
    async def test_non_member_rejected(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _raid_row(status="in_progress")
        conn.fetchval.return_value = None  # not a member
        user = _make_user("freelancer", user_id="outsider")

        with pytest.raises(PermissionError, match="raid members"):
            await quest_service.complete_raid_quest(conn, "raid_1", user)

    @pytest.mark.asyncio
    async def test_successful_complete(self):
        conn = _make_conn()
        completed_row = _raid_row(status="completed")
        conn.fetchrow.side_effect = [
            _raid_row(status="in_progress"),  # quest FOR UPDATE
            completed_row,                     # final quest read
        ]
        conn.fetchval.return_value = "part_fl1"  # is_member check
        conn.fetch.return_value = [_participant_row("fl1"), _participant_row("fl2", "tester")]
        user = _make_user("freelancer", user_id="fl1")

        result = await quest_service.complete_raid_quest(conn, "raid_1", user)
        assert result["message"] == "Raid quest completed — awaiting client confirmation"
        assert len(result["participants"]) == 2


class TestGetRaidParty:
    @pytest.mark.asyncio
    async def test_quest_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await quest_service.get_raid_party(conn, "raid_1")

    @pytest.mark.asyncio
    async def test_not_raid_rejected(self):
        conn = _make_conn()
        row = _quest_row()
        row["quest_type"] = "standard"
        row["raid_max_members"] = None
        row["raid_current_members"] = 0
        conn.fetchrow.return_value = row

        with pytest.raises(ValueError, match="not a raid"):
            await quest_service.get_raid_party(conn, "quest_1")

    @pytest.mark.asyncio
    async def test_returns_party(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _raid_row(raid_current_members=2)
        conn.fetch.return_value = [
            _participant_row("fl1", "leader"),
            _participant_row("fl2", "developer"),
        ]

        result = await quest_service.get_raid_party(conn, "raid_1")
        assert result.max_members == 4
        assert result.current_members == 2
        assert result.open_slots == 2
        assert len(result.participants) == 2
        assert result.role_slots == ["leader", "developer"]


# ---------------------------------------------------------------------------
# Legendary Quest Chains
# ---------------------------------------------------------------------------


def _chain_row(**overrides):
    """Fake quest_chains row."""
    now = datetime.now(timezone.utc)
    base = {
        "id": "chain_1",
        "title": "Legendary Path",
        "description": "Multi-step chain",
        "total_steps": 3,
        "final_xp_bonus": 100,
        "final_badge_id": None,
        "created_at": now,
    }
    base.update(overrides)
    return base


def _chain_step_row(chain_id="chain_1", quest_id="quest_1", step_order=1, **overrides):
    base = {
        "id": f"cs_{step_order}",
        "chain_id": chain_id,
        "quest_id": quest_id,
        "step_order": step_order,
    }
    base.update(overrides)
    return base


def _progress_row(chain_id="chain_1", user_id="fl_1", current_step=0, status="not_started", **overrides):
    now = datetime.now(timezone.utc)
    base = {
        "id": f"ucp_{user_id}_{chain_id}",
        "chain_id": chain_id,
        "user_id": user_id,
        "current_step": current_step,
        "status": status,
        "started_at": None,
        "completed_at": None,
    }
    base.update(overrides)
    return base


class TestListQuestChains:
    @pytest.mark.asyncio
    async def test_empty_list(self):
        conn = _make_conn()
        conn.fetch.return_value = []
        conn.fetchrow.return_value = {"cnt": 0}

        result = await quest_service.list_quest_chains(conn, page=1, page_size=20)
        assert result.total == 0
        assert result.chains == []

    @pytest.mark.asyncio
    async def test_returns_chains(self):
        conn = _make_conn()
        conn.fetch.return_value = [_chain_row(), _chain_row(id="chain_2", title="Second")]
        conn.fetchrow.return_value = {"cnt": 2}

        result = await quest_service.list_quest_chains(conn, page=1, page_size=20)
        assert result.total == 2
        assert len(result.chains) == 2
        assert result.chains[0].title == "Legendary Path"


class TestGetChainDetail:
    @pytest.mark.asyncio
    async def test_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None
        with pytest.raises(ValueError, match="Chain not found"):
            await quest_service.get_chain_detail(conn, "no_chain")

    @pytest.mark.asyncio
    async def test_returns_detail_with_quests(self):
        """Chain with 2 steps returns steps and quests in order."""
        conn = _make_conn()
        chain = _chain_row(total_steps=2)
        step1 = _chain_step_row(quest_id="q1", step_order=1)
        step2 = _chain_step_row(quest_id="q2", step_order=2)
        q1_row = _quest_row(quest_id="q1")
        q2_row = _quest_row(quest_id="q2")

        # fetchrow calls: first for chain, then for each quest, then no user progress
        conn.fetchrow.side_effect = [chain, q1_row, q2_row]
        conn.fetch.return_value = [step1, step2]

        result = await quest_service.get_chain_detail(conn, "chain_1", user_id=None)
        assert result.chain.total_steps == 2
        assert len(result.steps) == 2
        assert len(result.quests) == 2
        assert result.user_progress is None

    @pytest.mark.asyncio
    async def test_returns_detail_with_user_progress(self):
        conn = _make_conn()
        chain = _chain_row(total_steps=2)
        step1 = _chain_step_row(quest_id="q1", step_order=1)
        q1_row = _quest_row(quest_id="q1")
        progress = _progress_row(current_step=1, status="in_progress")

        conn.fetchrow.side_effect = [chain, q1_row, progress]
        conn.fetch.return_value = [step1]

        result = await quest_service.get_chain_detail(conn, "chain_1", user_id="fl_1")
        assert result.user_progress is not None
        assert result.user_progress.current_step == 1


class TestCreateQuestChain:
    @pytest.mark.asyncio
    async def test_non_admin_rejected(self):
        conn = _make_conn()
        from app.models.quest import QuestChainCreate
        data = QuestChainCreate(title="Chain", description="Desc for chain test", quest_ids=["q1", "q2"])
        user = _make_user(role="freelancer", user_id="fl_1")
        with pytest.raises(PermissionError, match="Only admins"):
            await quest_service.create_quest_chain(conn, data, user)

    @pytest.mark.asyncio
    async def test_quest_not_found(self):
        conn = _make_conn()
        conn.fetchrow.return_value = None  # quest not found
        from app.models.quest import QuestChainCreate
        data = QuestChainCreate(title="Chain", description="Desc for chain test", quest_ids=["q1", "q2"])
        admin = _make_user(role="admin", user_id="admin_1")
        with pytest.raises(ValueError, match="Quest q1 not found"):
            await quest_service.create_quest_chain(conn, data, admin)

    @pytest.mark.asyncio
    async def test_admin_creates_chain(self):
        conn = _make_conn()
        from app.models.quest import QuestChainCreate
        data = QuestChainCreate(title="Chain", description="Desc for chain test", quest_ids=["q1", "q2"], final_xp_bonus=50)
        admin = _make_user(role="admin", user_id="admin_1")

        # validate quest existence
        conn.fetchrow.side_effect = [
            {"id": "q1"},  # quest q1 exists
            {"id": "q2"},  # quest q2 exists
            # get_chain_detail calls:
            _chain_row(total_steps=2),  # chain row
            _quest_row(quest_id="q1"),  # quest q1
            _quest_row(quest_id="q2"),  # quest q2
        ]
        conn.fetch.return_value = [
            _chain_step_row(quest_id="q1", step_order=1),
            _chain_step_row(quest_id="q2", step_order=2),
        ]

        result = await quest_service.create_quest_chain(conn, data, admin)
        assert result.chain.total_steps == 2
        assert len(result.steps) == 2


class TestAdvanceChainProgress:
    @pytest.mark.asyncio
    async def test_no_chain_returns_none(self):
        """Quest not in a chain returns None."""
        conn = _make_conn()
        conn.fetchrow.return_value = None
        result = await quest_service.advance_chain_progress(conn, "quest_1", "fl_1")
        assert result is None

    @pytest.mark.asyncio
    async def test_creates_new_progress(self):
        conn = _make_conn()
        step_row = {"chain_id": "chain_1", "step_order": 1}
        chain = _chain_row(total_steps=3)
        progress_after = _progress_row(current_step=1, status="in_progress")

        conn.fetchrow.side_effect = [
            step_row,   # chain_steps lookup
            chain,      # chain lookup
            None,       # no existing progress (FOR UPDATE)
            progress_after,  # after insert
        ]

        result = await quest_service.advance_chain_progress(conn, "quest_1", "fl_1")
        assert result is not None
        assert result.current_step == 1
        assert result.status == "in_progress"

    @pytest.mark.asyncio
    async def test_advances_existing_progress(self):
        conn = _make_conn()
        step_row = {"chain_id": "chain_1", "step_order": 2}
        chain = _chain_row(total_steps=3)
        existing_progress = _progress_row(current_step=1, status="in_progress")
        updated_progress = _progress_row(current_step=2, status="in_progress")

        conn.fetchrow.side_effect = [
            step_row,    # chain_steps lookup
            chain,       # chain lookup
            existing_progress,  # FOR UPDATE
            updated_progress,   # after update
        ]

        result = await quest_service.advance_chain_progress(conn, "quest_2", "fl_1")
        assert result is not None
        assert result.current_step == 2

    @pytest.mark.asyncio
    async def test_completes_chain_on_final_step(self):
        conn = _make_conn()
        step_row = {"chain_id": "chain_1", "step_order": 3}
        chain = _chain_row(total_steps=3, final_xp_bonus=100, final_badge_id=None)
        existing_progress = _progress_row(current_step=2, status="in_progress")
        completed_progress = _progress_row(current_step=3, status="completed")

        # user for XP bonus
        user_row = _user_row(user_id="fl_1", xp=50)

        conn.fetchrow.side_effect = [
            step_row,           # chain_steps lookup
            chain,              # chain lookup
            existing_progress,  # FOR UPDATE
            user_row,           # user FOR UPDATE for XP
            completed_progress, # after update
        ]

        with patch("app.services.quest_service.check_level_up") as mock_check:
            mock_check.return_value = (False, GradeEnum.novice, 1, [])
            result = await quest_service.advance_chain_progress(conn, "quest_3", "fl_1")

        assert result is not None
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_does_not_go_backwards(self):
        """Completing a step that's already behind current_step doesn't regress."""
        conn = _make_conn()
        step_row = {"chain_id": "chain_1", "step_order": 1}
        chain = _chain_row(total_steps=3)
        existing_progress = _progress_row(current_step=2, status="in_progress")

        conn.fetchrow.side_effect = [
            step_row,
            chain,
            existing_progress,
        ]

        result = await quest_service.advance_chain_progress(conn, "quest_1", "fl_1")
        # step_order=1 <= current_step=2, so no advance
        assert result.current_step == 2


class TestGetUserChainProgressList:
    @pytest.mark.asyncio
    async def test_empty(self):
        conn = _make_conn()
        conn.fetch.return_value = []
        result = await quest_service.get_user_chain_progress_list(conn, "fl_1")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_progress_entries(self):
        conn = _make_conn()
        conn.fetch.return_value = [
            _progress_row(chain_id="chain_1", current_step=2, status="in_progress"),
            _progress_row(chain_id="chain_2", current_step=1, status="in_progress"),
        ]
        result = await quest_service.get_user_chain_progress_list(conn, "fl_1")
        assert len(result) == 2
        assert result[0].chain_id == "chain_1"
