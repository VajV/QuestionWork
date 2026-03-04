"""Tests for the class engine (app.core.classes) — pure functions, no DB."""

import pytest

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
