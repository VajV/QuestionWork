"""Tests for BadgeService — check_and_award, get_user_badges, get_badge_catalogue."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.badge_service import (
    check_and_award,
    get_user_badges,
    get_badge_catalogue,
    _meets_criteria,
)
from app.models.badge_notification import BadgeAwardResult, UserBadgeEarned


# ────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────

def _make_conn(in_txn=True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_txn)
    return conn


def _badge(
    bid="badge_quest1",
    name="First Quest",
    description="Complete your first quest",
    icon="🏅",
    criteria_type="quests_completed",
    criteria_value=1,
):
    return {
        "id": bid,
        "name": name,
        "description": description,
        "icon": icon,
        "criteria_type": criteria_type,
        "criteria_value": criteria_value,
        "created_at": datetime.now(timezone.utc),
    }


# ────────────────────────────────────────────
# _meets_criteria unit tests
# ────────────────────────────────────────────

class TestMeetsCriteria:
    def test_quests_completed_pass(self):
        assert _meets_criteria("quests_completed", 5, {"quests_completed": 5}) is True

    def test_quests_completed_fail(self):
        assert _meets_criteria("quests_completed", 5, {"quests_completed": 4}) is False

    def test_level_pass(self):
        assert _meets_criteria("level", 10, {"level": 15}) is True

    def test_level_fail(self):
        assert _meets_criteria("level", 10, {"level": 9}) is False

    def test_xp_pass(self):
        assert _meets_criteria("xp", 1000, {"xp": 1000}) is True

    def test_xp_fail(self):
        assert _meets_criteria("xp", 1000, {"xp": 999}) is False

    def test_earnings_pass(self):
        assert _meets_criteria("earnings", 100.0, {"earnings": 200.0}) is True

    def test_grade_junior_pass(self):
        assert _meets_criteria("grade_junior", 1, {"grade": "junior"}) is True

    def test_grade_junior_also_middle(self):
        assert _meets_criteria("grade_junior", 1, {"grade": "middle"}) is True

    def test_grade_junior_novice_fail(self):
        assert _meets_criteria("grade_junior", 1, {"grade": "novice"}) is False

    def test_grade_middle_pass(self):
        assert _meets_criteria("grade_middle", 1, {"grade": "middle"}) is True

    def test_grade_senior_pass(self):
        assert _meets_criteria("grade_senior", 1, {"grade": "senior"}) is True

    def test_grade_senior_junior_fail(self):
        assert _meets_criteria("grade_senior", 1, {"grade": "junior"}) is False

    def test_unknown_criteria_false(self):
        assert _meets_criteria("unknown_type", 1, {"anything": 99}) is False


# ────────────────────────────────────────────
# check_and_award
# ────────────────────────────────────────────

class TestCheckAndAward:
    @pytest.mark.asyncio
    async def test_awards_new_badge_when_criteria_met(self):
        conn = _make_conn()
        badge = _badge()
        conn.fetch.side_effect = [
            [badge],          # catalogue
            [],               # already earned (empty)
        ]
        conn.execute = AsyncMock()

        event_data = {"quests_completed": 1}
        result = await check_and_award(conn, "user1", "quest_completed", event_data)

        assert len(result.newly_earned) == 1
        assert result.newly_earned[0].badge_id == badge["id"]
        assert result.newly_earned[0].badge_name == badge["name"]
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_already_earned_badge(self):
        conn = _make_conn()
        badge = _badge()
        conn.fetch.side_effect = [
            [badge],
            [{"badge_id": badge["id"]}],  # already earned
        ]

        result = await check_and_award(conn, "user1", "quest_completed", {"quests_completed": 1})

        assert result.newly_earned == []
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_badge_when_criteria_not_met(self):
        conn = _make_conn()
        badge = _badge(criteria_value=10)
        conn.fetch.side_effect = [
            [badge],
            [],
        ]

        result = await check_and_award(conn, "user1", "quest_completed", {"quests_completed": 5})

        assert result.newly_earned == []
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_awards_multiple_badges(self):
        conn = _make_conn()
        b1 = _badge("b1", criteria_value=1)
        b2 = _badge("b2", name="Veteran", criteria_value=5)
        conn.fetch.side_effect = [
            [b1, b2],
            [],
        ]
        conn.execute = AsyncMock()

        result = await check_and_award(conn, "user1", "quest_completed", {"quests_completed": 5})

        assert len(result.newly_earned) == 2
        assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_if_not_in_transaction(self):
        conn = _make_conn(in_txn=False)

        with pytest.raises(RuntimeError, match="DB transaction"):
            await check_and_award(conn, "user1", "quest_completed", {})

    @pytest.mark.asyncio
    async def test_empty_catalogue_returns_empty_result(self):
        conn = _make_conn()
        conn.fetch.side_effect = [[], []]

        result = await check_and_award(conn, "user1", "quest_completed", {"quests_completed": 100})

        assert result.newly_earned == []


# ────────────────────────────────────────────
# get_user_badges
# ────────────────────────────────────────────

class TestGetUserBadges:
    @pytest.mark.asyncio
    async def test_returns_earned_badges(self):
        conn = _make_conn()
        now = datetime.now(timezone.utc)
        conn.fetch = AsyncMock(return_value=[
            {
                "id": "ub1",
                "user_id": "user1",
                "badge_id": "badge_quest1",
                "name": "First Quest",
                "description": "Complete your first quest",
                "icon": "🏅",
                "earned_at": now,
            }
        ])

        result = await get_user_badges(conn, "user1")

        assert len(result) == 1
        assert result[0].badge_id == "badge_quest1"
        assert result[0].badge_name == "First Quest"

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_badges(self):
        conn = _make_conn()
        conn.fetch = AsyncMock(return_value=[])

        result = await get_user_badges(conn, "user_no_badges")

        assert result == []


# ────────────────────────────────────────────
# get_badge_catalogue
# ────────────────────────────────────────────

class TestGetBadgeCatalogue:
    @pytest.mark.asyncio
    async def test_returns_all_badges(self):
        conn = _make_conn()
        now = datetime.now(timezone.utc)
        conn.fetch = AsyncMock(return_value=[
            {
                "id": "b1",
                "name": "First Quest",
                "description": "...",
                "icon": "🏅",
                "criteria_type": "quests_completed",
                "criteria_value": 1,
            },
        ])

        result = await get_badge_catalogue(conn)

        assert len(result) == 1
        assert result[0]["id"] == "b1"
