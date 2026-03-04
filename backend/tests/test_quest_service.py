"""Tests for quest_service — unit tests with mocked asyncpg connection."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

import contextlib

from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats
from app.models.quest import QuestApplicationCreate, QuestCreate, QuestStatusEnum
from app.services import quest_service


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


def _make_user(role="client", user_id="user_client", grade=GradeEnum.novice):
    return UserProfile(
        id=user_id,
        username=f"test_{role}",
        role=UserRoleEnum(role),
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
    budget=5000.0,
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
    }


def _user_row(user_id="user_freelancer", grade="novice", xp=0, level=1):
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
        "xp_to_next": 100,
        "stats_int": 10,
        "stats_dex": 10,
        "stats_cha": 10,
        "stat_points": 0,
        "badges": "[]",
        "bio": None,
        "skills": "[]",
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


# ---------------------------------------------------------------------------
# create_quest
# ---------------------------------------------------------------------------


class TestCreateQuest:
    @pytest.mark.asyncio
    async def test_creates_quest(self):
        conn = _make_conn()
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
        conn.execute.assert_called_once()


# ---------------------------------------------------------------------------
# apply_to_quest
# ---------------------------------------------------------------------------


class TestApplyToQuest:
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


# ---------------------------------------------------------------------------
# mark_quest_complete
# ---------------------------------------------------------------------------


class TestMarkQuestComplete:
    @pytest.mark.asyncio
    async def test_not_assigned_freelancer(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(
            status="in_progress", assigned_to="other_user"
        )
        user = _make_user("freelancer", "user_fl")

        with pytest.raises(PermissionError, match="assigned"):
            await quest_service.mark_quest_complete(conn, "quest_1", user)

    @pytest.mark.asyncio
    async def test_quest_not_in_progress(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row(status="open")
        user = _make_user("freelancer", "user_fl")

        with pytest.raises(ValueError, match="in progress"):
            await quest_service.mark_quest_complete(conn, "quest_1", user)


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
        conn.fetchrow.return_value = _quest_row(status="open")
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
        conn = _make_conn()

        # fetchrow sequence: quest, freelancer, freelancer wallet, platform wallet
        quest = _quest_row(status="completed", assigned_to="user_fl")
        freelancer = _user_row(user_id="user_fl", xp=100, grade="novice")

        conn.fetchrow.side_effect = [
            quest,
            freelancer,
            None,  # freelancer wallet → INSERT path in split_payment
            None,  # platform wallet → INSERT path
            {"character_class": None},  # class_service.add_class_xp → user has no class
        ]

        class _FakeTransaction:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        conn.transaction = MagicMock(return_value=_FakeTransaction())

        user = _make_user("client")
        result = await quest_service.confirm_quest_completion(conn, "quest_1", user)

        # Verify transaction() was called (atomic wrapper)
        conn.transaction.assert_called_once()

        assert "confirmed" in result["message"].lower() or "reward" in result["message"].lower()
        assert result["xp_reward"] > 0
        assert "platform_fee" in result
        assert "fee_percent" in result
        assert "stat_delta" in result
        assert result["stat_delta"]["int"] >= 0


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
