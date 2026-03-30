"""Tests for the class engine (app.core.classes) — pure functions, no DB."""

from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.classes import (
    BonusType,
    ClassId,
    CLASS_LEVEL_THRESHOLDS,
    CLASS_REGISTRY,
    calculate_class_xp_multiplier,
    class_level_from_xp,
    class_participation_ratio,
    class_xp_to_next,
    get_all_classes,
    get_available_classes,
    get_class_config,
    should_block_quest,
)
from app.db.session import get_db_connection
from app.main import app
from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats


class _AsyncTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_user() -> UserProfile:
    return UserProfile(
        id="class_test_user",
        username="classhero",
        email="classhero@example.com",
        role=UserRoleEnum.freelancer,
        level=6,
        grade=GradeEnum.novice,
        xp=250,
        xp_to_next=300,
        stats=UserStats(int=10, dex=11, cha=9),
        badges=[],
        bio="",
        skills=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def client():
    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
    ):
        async def _mock_conn_dep():
            conn = AsyncMock()
            conn.transaction = lambda: _AsyncTransaction()
            return conn

        app.dependency_overrides[get_db_connection] = _mock_conn_dep
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
        app.dependency_overrides.pop(get_db_connection, None)


class TestClassRegistry:
    def test_berserk_exists(self):
        cfg = get_class_config("berserk")
        assert cfg is not None
        assert cfg.id == ClassId.berserk
        assert cfg.name_ru == "Берсерк"

    def test_unknown_class_returns_none(self):
        assert get_class_config("wizard") is None

    def test_get_all_classes(self):
        all_cls = get_all_classes()
        assert len(all_cls) >= 1
        assert all_cls[0].id == ClassId.berserk

    def test_get_available_by_level(self):
        # Level 1 — nothing available (min is 5)
        avail = get_available_classes(1)
        assert len(avail) == 0

        # Level 5 — berserk available
        avail = get_available_classes(5)
        assert any(c.id == ClassId.berserk for c in avail)


class TestClassLevelProgression:
    def test_level_from_xp_zero(self):
        assert class_level_from_xp(0) == 1

    def test_level_from_xp_threshold_exact(self):
        assert class_level_from_xp(500) == 2  # threshold[2] = 1500, xp=500 >= threshold[1]=500 → level 2

    def test_level_from_xp_high(self):
        assert class_level_from_xp(50000) == 10

    def test_level_from_xp_beyond_max(self):
        assert class_level_from_xp(999999) == 10

    def test_xp_to_next_level_1(self):
        # Level 1 needs 500 XP (threshold[1]) to reach level 2
        assert class_xp_to_next(0, 1) == 500

    def test_xp_to_next_at_max_level(self):
        assert class_xp_to_next(50000, 10) == 0


class TestClassParticipation:
    def test_urgent_quest_full_ratio(self):
        ratio = class_participation_ratio(ClassId.berserk, is_urgent=True, required_portfolio=False)
        assert ratio == 1.0

    def test_neutral_quest_half_ratio(self):
        ratio = class_participation_ratio(ClassId.berserk, is_urgent=False, required_portfolio=False)
        assert ratio == 0.5

    def test_contradicting_quest_zero_ratio(self):
        # Portfolio quest for berserk = contradiction (portfolio_blocked weakness)
        ratio = class_participation_ratio(ClassId.berserk, is_urgent=False, required_portfolio=True)
        assert ratio == 0.0


class TestClassXpMultiplier:
    def test_berserk_urgent_bonus(self):
        mult = calculate_class_xp_multiplier("berserk", is_urgent=True)
        # berserk has +20% XP for urgent quests
        assert mult == pytest.approx(1.2)

    def test_berserk_non_urgent_no_bonus(self):
        mult = calculate_class_xp_multiplier("berserk", is_urgent=False)
        assert mult == pytest.approx(1.0)


class TestShouldBlockQuest:
    def test_berserk_blocks_portfolio(self):
        assert should_block_quest("berserk", required_portfolio=True) is True

    def test_berserk_allows_non_portfolio(self):
        assert should_block_quest("berserk", required_portfolio=False) is False


class TestAbilityActivationEndpoint:
    def test_activate_ability_accepts_path_param_route(self, client):
        from app.api.deps import require_auth

        app.dependency_overrides[require_auth] = lambda: _make_user()
        try:
            with patch("app.api.v1.endpoints.classes.class_service.activate_ability", new=AsyncMock(return_value={
                "message": "ok",
                "ability": {
                    "ability_id": "rage_mode",
                    "name": "Rage Mode",
                    "name_ru": "Режим ярости",
                    "description_ru": "desc",
                    "icon": "💀",
                    "required_class_level": 5,
                    "cooldown_hours": 72,
                    "duration_hours": 4,
                    "effects": {"xp_all_bonus": 0.5},
                    "is_unlocked": True,
                    "is_active": True,
                    "active_until": None,
                    "is_on_cooldown": True,
                    "cooldown_until": None,
                    "times_used": 1,
                },
            })) as activate_mock:
                response = client.post("/api/v1/classes/abilities/rage_mode/activate")

            assert response.status_code == 200
            activate_mock.assert_awaited_once()
            assert activate_mock.await_args.args[2] == "rage_mode"
        finally:
            app.dependency_overrides.pop(require_auth, None)
