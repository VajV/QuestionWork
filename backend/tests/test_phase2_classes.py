"""Tests for Phase 2 class system — perks, abilities, perk helpers.

Pure-function tests (no DB required) for the class engine additions.
"""

import pytest

from app.core.classes import (
    ClassId,
    get_class_config,
    get_class_perks,
    get_perk_config,
    calculate_perk_points_available,
    can_unlock_perk,
    get_class_abilities,
    get_ability_config,
    PerkConfig,
    AbilityConfig,
)


# ────────────────────────────────────────────
# Perk registry tests
# ────────────────────────────────────────────

class TestBerserkerPerks:
    def test_berserk_has_six_perks(self):
        perks = get_class_perks("berserk")
        assert len(perks) == 6

    def test_perks_sorted_by_tier(self):
        perks = get_class_perks("berserk")
        tiers = [p.tier for p in perks]
        assert tiers == sorted(tiers)

    def test_tier1_perks(self):
        perks = get_class_perks("berserk")
        t1 = [p for p in perks if p.tier == 1]
        assert len(t1) == 3
        ids = {p.id for p in t1}
        assert "berserk_adrenaline" in ids
        assert "berserk_thick_skin" in ids
        assert "berserk_battle_cry" in ids

    def test_tier2_perks(self):
        perks = get_class_perks("berserk")
        t2 = [p for p in perks if p.tier == 2]
        assert len(t2) == 2
        ids = {p.id for p in t2}
        assert "berserk_fury" in ids
        assert "berserk_iron_will" in ids

    def test_tier3_perk(self):
        perks = get_class_perks("berserk")
        t3 = [p for p in perks if p.tier == 3]
        assert len(t3) == 1
        assert t3[0].id == "berserk_warlord"

    def test_perk_lookup(self):
        perk = get_perk_config("berserk", "berserk_adrenaline")
        assert perk is not None
        assert perk.name_ru == "Адреналиновый прилив"
        assert perk.tier == 1
        assert perk.perk_point_cost == 1

    def test_perk_lookup_unknown(self):
        assert get_perk_config("berserk", "nonexistent") is None

    def test_perk_lookup_wrong_class(self):
        assert get_perk_config("wizard", "berserk_adrenaline") is None

    def test_warlord_prerequisites(self):
        perk = get_perk_config("berserk", "berserk_warlord")
        assert perk is not None
        assert set(perk.prerequisite_ids) == {"berserk_fury", "berserk_iron_will"}

    def test_adrenaline_effects(self):
        perk = get_perk_config("berserk", "berserk_adrenaline")
        assert perk is not None
        assert perk.effects.get("xp_urgent_bonus_extra") == 0.10

    def test_thick_skin_effects(self):
        perk = get_perk_config("berserk", "berserk_thick_skin")
        assert perk is not None
        assert perk.effects.get("burnout_threshold_bonus") == 2

    def test_warlord_effects(self):
        perk = get_perk_config("berserk", "berserk_warlord")
        assert perk is not None
        assert perk.effects.get("extra_quest_slot_bonus") == 1
        assert perk.effects.get("remove_premium_penalty") is True

    def test_empty_class_perks(self):
        perks = get_class_perks("nonexistent")
        assert perks == []


# ────────────────────────────────────────────
# Perk points calculator
# ────────────────────────────────────────────

class TestPerkPoints:
    def test_level_1_no_points(self):
        assert calculate_perk_points_available(1) == 0

    def test_level_2_one_point(self):
        assert calculate_perk_points_available(2) == 1

    def test_level_5(self):
        assert calculate_perk_points_available(5) == 4

    def test_level_10(self):
        assert calculate_perk_points_available(10) == 9

    def test_custom_per_level(self):
        assert calculate_perk_points_available(5, 2) == 8  # (5-1)*2

    def test_level_zero_or_negative(self):
        assert calculate_perk_points_available(0) == 0
        assert calculate_perk_points_available(-1) == 0


# ────────────────────────────────────────────
# can_unlock_perk logic
# ────────────────────────────────────────────

class TestCanUnlockPerk:
    @pytest.fixture
    def adrenaline(self):
        return get_perk_config("berserk", "berserk_adrenaline")

    @pytest.fixture
    def fury(self):
        return get_perk_config("berserk", "berserk_fury")

    @pytest.fixture
    def warlord(self):
        return get_perk_config("berserk", "berserk_warlord")

    def test_can_unlock_basic(self, adrenaline):
        ok, reason = can_unlock_perk(adrenaline, class_level=2, owned_perk_ids=set(), available_points=1)
        assert ok is True
        assert reason == "ok"

    def test_already_unlocked(self, adrenaline):
        ok, reason = can_unlock_perk(adrenaline, class_level=5, owned_perk_ids={"berserk_adrenaline"}, available_points=5)
        assert ok is False
        assert "уже разблокирован" in reason.lower()

    def test_level_too_low(self, adrenaline):
        ok, reason = can_unlock_perk(adrenaline, class_level=1, owned_perk_ids=set(), available_points=5)
        assert ok is False
        assert "уровень" in reason.lower()

    def test_not_enough_points(self, adrenaline):
        ok, reason = can_unlock_perk(adrenaline, class_level=5, owned_perk_ids=set(), available_points=0)
        assert ok is False
        assert "очков" in reason.lower()

    def test_missing_prerequisite(self, fury):
        ok, reason = can_unlock_perk(fury, class_level=5, owned_perk_ids=set(), available_points=5)
        assert ok is False
        assert "berserk_adrenaline" in reason

    def test_prerequisite_met(self, fury):
        ok, reason = can_unlock_perk(
            fury, class_level=5,
            owned_perk_ids={"berserk_adrenaline"},
            available_points=5,
        )
        assert ok is True

    def test_warlord_needs_both_prereqs(self, warlord):
        ok1, _ = can_unlock_perk(warlord, class_level=7, owned_perk_ids={"berserk_fury"}, available_points=5)
        assert ok1 is False  # missing iron_will

        ok2, _ = can_unlock_perk(
            warlord, class_level=7,
            owned_perk_ids={"berserk_fury", "berserk_iron_will"},
            available_points=3,
        )
        assert ok2 is True

    def test_warlord_not_enough_points(self, warlord):
        ok, reason = can_unlock_perk(
            warlord, class_level=7,
            owned_perk_ids={"berserk_fury", "berserk_iron_will"},
            available_points=2,
        )
        assert ok is False
        assert "очков" in reason.lower()


# ────────────────────────────────────────────
# Ability registry tests
# ────────────────────────────────────────────

class TestBerserkerAbilities:
    def test_berserk_has_rage_mode(self):
        abilities = get_class_abilities("berserk")
        assert len(abilities) == 1
        assert abilities[0].id == "rage_mode"

    def test_rage_mode_config(self):
        ability = get_ability_config("berserk", "rage_mode")
        assert ability is not None
        assert ability.name_ru == "Режим ярости"
        assert ability.required_class_level == 5
        assert ability.cooldown_hours == 72
        assert ability.duration_hours == 4

    def test_rage_mode_effects(self):
        ability = get_ability_config("berserk", "rage_mode")
        assert ability is not None
        assert ability.effects.get("xp_all_bonus") == 0.50
        assert ability.effects.get("burnout_immune") is True
        assert ability.effects.get("post_rage_burnout_hours") == 12

    def test_ability_lookup_unknown(self):
        assert get_ability_config("berserk", "nonexistent") is None

    def test_ability_lookup_wrong_class(self):
        assert get_ability_config("wizard", "rage_mode") is None

    def test_empty_class_abilities(self):
        assert get_class_abilities("nonexistent") == []


# ────────────────────────────────────────────
# ClassConfig integration tests
# ────────────────────────────────────────────

class TestClassConfigPhase2:
    def test_berserk_config_has_perks(self):
        cfg = get_class_config("berserk")
        assert cfg is not None
        assert len(cfg.perks) == 6

    def test_berserk_config_has_abilities(self):
        cfg = get_class_config("berserk")
        assert cfg is not None
        assert len(cfg.abilities) == 1

    def test_berserk_perk_points_per_level(self):
        cfg = get_class_config("berserk")
        assert cfg is not None
        assert cfg.perk_points_per_level == 1

    def test_berserk_stat_bias(self):
        cfg = get_class_config("berserk")
        assert cfg is not None
        assert cfg.stat_bias == {"dex": 2, "int": 0, "cha": 1}

    def test_perk_is_frozen(self):
        perk = get_perk_config("berserk", "berserk_adrenaline")
        assert perk is not None
        with pytest.raises(Exception):
            perk.id = "hacked"  # type: ignore

    def test_ability_is_frozen(self):
        ability = get_ability_config("berserk", "rage_mode")
        assert ability is not None
        with pytest.raises(Exception):
            ability.id = "hacked"  # type: ignore
