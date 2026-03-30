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


class TestAbilityContractAlignment:
    def test_alchemist_active_ability_has_deadline_penalty_reduce_effect(self):
        ability = get_ability_config("alchemist", "transmutation")
        assert ability is not None
        assert ability.effects.get("deadline_penalty_reduce") == 0.10

    def test_paladin_active_ability_has_cancel_xp_protect_effect(self):
        ability = get_ability_config("paladin", "divine_protection")
        assert ability is not None
        assert ability.effects.get("cancel_xp_protect") is True

    def test_rogue_active_ability_has_urgent_payout_bonus_effect(self):
        ability = get_ability_config("rogue", "vanish")
        assert ability is not None
        assert ability.effects.get("urgent_payout_bonus") == 0.10


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


# ────────────────────────────────────────────
# Rogue perk tree
# ────────────────────────────────────────────

class TestRoguePerks:
    def test_rogue_has_five_perks(self):
        perks = get_class_perks("rogue")
        assert len(perks) == 5

    def test_perks_sorted_by_tier(self):
        perks = get_class_perks("rogue")
        tiers = [p.tier for p in perks]
        assert tiers == sorted(tiers)

    def test_tier1_perks(self):
        perks = get_class_perks("rogue")
        t1 = [p for p in perks if p.tier == 1]
        assert len(t1) == 2
        ids = {p.id for p in t1}
        assert "rogue_quick_draw" in ids
        assert "rogue_shadow_step" in ids

    def test_tier2_perks(self):
        perks = get_class_perks("rogue")
        t2 = [p for p in perks if p.tier == 2]
        assert len(t2) == 2
        ids = {p.id for p in t2}
        assert "rogue_smoke_screen" in ids
        assert "rogue_black_market" in ids

    def test_tier3_perk(self):
        perks = get_class_perks("rogue")
        t3 = [p for p in perks if p.tier == 3]
        assert len(t3) == 1
        assert t3[0].id == "rogue_phantom"

    def test_perk_lookup(self):
        perk = get_perk_config("rogue", "rogue_quick_draw")
        assert perk is not None
        assert perk.name_ru == "Быстрый старт"
        assert perk.tier == 1
        assert perk.perk_point_cost == 1

    def test_smoke_screen_prerequisite(self):
        perk = get_perk_config("rogue", "rogue_smoke_screen")
        assert perk is not None
        assert perk.prerequisite_ids == ["rogue_quick_draw"]

    def test_black_market_prerequisite(self):
        perk = get_perk_config("rogue", "rogue_black_market")
        assert perk is not None
        assert perk.prerequisite_ids == ["rogue_shadow_step"]

    def test_phantom_prerequisites(self):
        perk = get_perk_config("rogue", "rogue_phantom")
        assert perk is not None
        assert set(perk.prerequisite_ids) == {"rogue_quick_draw", "rogue_shadow_step"}

    def test_quick_draw_effects(self):
        perk = get_perk_config("rogue", "rogue_quick_draw")
        assert perk is not None
        assert perk.effects.get("first_apply_bonus_extra") == 0.10

    def test_black_market_effects(self):
        perk = get_perk_config("rogue", "rogue_black_market")
        assert perk is not None
        assert perk.effects.get("extra_quest_slot_bonus") == 1

    def test_phantom_effects(self):
        perk = get_perk_config("rogue", "rogue_phantom")
        assert perk is not None
        assert perk.effects.get("first_apply_bonus_extra") == 0.10
        assert perk.effects.get("chain_bonus") == 0.10

    def test_phantom_tier3_cost(self):
        perk = get_perk_config("rogue", "rogue_phantom")
        assert perk is not None
        assert perk.perk_point_cost == 3

    def test_unlock_phantom_needs_both_prereqs(self):
        phantom = get_perk_config("rogue", "rogue_phantom")
        assert phantom is not None
        ok1, _ = can_unlock_perk(phantom, class_level=7, owned_perk_ids={"rogue_quick_draw"}, available_points=5)
        assert ok1 is False  # missing shadow_step
        ok2, _ = can_unlock_perk(
            phantom, class_level=7,
            owned_perk_ids={"rogue_quick_draw", "rogue_shadow_step"},
            available_points=3,
        )
        assert ok2 is True


# ────────────────────────────────────────────
# Alchemist perk tree
# ────────────────────────────────────────────

class TestAlchemistPerks:
    def test_alchemist_has_five_perks(self):
        perks = get_class_perks("alchemist")
        assert len(perks) == 5

    def test_perks_sorted_by_tier(self):
        perks = get_class_perks("alchemist")
        tiers = [p.tier for p in perks]
        assert tiers == sorted(tiers)

    def test_tier1_perks(self):
        perks = get_class_perks("alchemist")
        t1 = [p for p in perks if p.tier == 1]
        assert len(t1) == 2
        ids = {p.id for p in t1}
        assert "alchemist_catalyst" in ids
        assert "alchemist_transmute" in ids

    def test_tier2_perks(self):
        perks = get_class_perks("alchemist")
        t2 = [p for p in perks if p.tier == 2]
        assert len(t2) == 2
        ids = {p.id for p in t2}
        assert "alchemist_stabilizer" in ids
        assert "alchemist_gold_touch" in ids

    def test_tier3_perk(self):
        perks = get_class_perks("alchemist")
        t3 = [p for p in perks if p.tier == 3]
        assert len(t3) == 1
        assert t3[0].id == "alchemist_philosophers_stone"

    def test_perk_lookup(self):
        perk = get_perk_config("alchemist", "alchemist_catalyst")
        assert perk is not None
        assert perk.name_ru == "Катализатор"
        assert perk.tier == 1
        assert perk.perk_point_cost == 1

    def test_stabilizer_prerequisite(self):
        perk = get_perk_config("alchemist", "alchemist_stabilizer")
        assert perk is not None
        assert perk.prerequisite_ids == ["alchemist_catalyst"]

    def test_gold_touch_prerequisite(self):
        perk = get_perk_config("alchemist", "alchemist_gold_touch")
        assert perk is not None
        assert perk.prerequisite_ids == ["alchemist_transmute"]

    def test_philosophers_stone_prerequisites(self):
        perk = get_perk_config("alchemist", "alchemist_philosophers_stone")
        assert perk is not None
        assert set(perk.prerequisite_ids) == {"alchemist_catalyst", "alchemist_transmute"}

    def test_catalyst_effects(self):
        perk = get_perk_config("alchemist", "alchemist_catalyst")
        assert perk is not None
        assert perk.effects.get("stale_bonus_extra") == 0.10

    def test_stabilizer_effects(self):
        perk = get_perk_config("alchemist", "alchemist_stabilizer")
        assert perk is not None
        assert perk.effects.get("urgent_penalty_reduction") == 0.05

    def test_philosophers_stone_effects(self):
        perk = get_perk_config("alchemist", "alchemist_philosophers_stone")
        assert perk is not None
        assert perk.effects.get("stale_bonus_extra") == 0.15

    def test_philosophers_stone_tier3_cost(self):
        perk = get_perk_config("alchemist", "alchemist_philosophers_stone")
        assert perk is not None
        assert perk.perk_point_cost == 3

    def test_unlock_philosophers_stone_needs_both_prereqs(self):
        stone = get_perk_config("alchemist", "alchemist_philosophers_stone")
        assert stone is not None
        ok1, _ = can_unlock_perk(stone, class_level=7, owned_perk_ids={"alchemist_catalyst"}, available_points=5)
        assert ok1 is False  # missing transmute
        ok2, _ = can_unlock_perk(
            stone, class_level=7,
            owned_perk_ids={"alchemist_catalyst", "alchemist_transmute"},
            available_points=3,
        )
        assert ok2 is True


# ────────────────────────────────────────────
# Paladin perk tree
# ────────────────────────────────────────────

class TestPaladinPerks:
    def test_paladin_has_five_perks(self):
        perks = get_class_perks("paladin")
        assert len(perks) == 5

    def test_perks_sorted_by_tier(self):
        perks = get_class_perks("paladin")
        tiers = [p.tier for p in perks]
        assert tiers == sorted(tiers)

    def test_tier1_perks(self):
        perks = get_class_perks("paladin")
        t1 = [p for p in perks if p.tier == 1]
        assert len(t1) == 2
        ids = {p.id for p in t1}
        assert "paladin_oath" in ids
        assert "paladin_bulwark" in ids

    def test_tier2_perks(self):
        perks = get_class_perks("paladin")
        t2 = [p for p in perks if p.tier == 2]
        assert len(t2) == 2
        ids = {p.id for p in t2}
        assert "paladin_sanctuary" in ids
        assert "paladin_blessed_hands" in ids

    def test_tier3_perk(self):
        perks = get_class_perks("paladin")
        t3 = [p for p in perks if p.tier == 3]
        assert len(t3) == 1
        assert t3[0].id == "paladin_champion"

    def test_perk_lookup(self):
        perk = get_perk_config("paladin", "paladin_oath")
        assert perk is not None
        assert perk.name_ru == "Клятва"
        assert perk.tier == 1
        assert perk.perk_point_cost == 1

    def test_sanctuary_prerequisite(self):
        perk = get_perk_config("paladin", "paladin_sanctuary")
        assert perk is not None
        assert perk.prerequisite_ids == ["paladin_oath"]

    def test_blessed_hands_prerequisite(self):
        perk = get_perk_config("paladin", "paladin_blessed_hands")
        assert perk is not None
        assert perk.prerequisite_ids == ["paladin_bulwark"]

    def test_champion_prerequisites(self):
        perk = get_perk_config("paladin", "paladin_champion")
        assert perk is not None
        assert set(perk.prerequisite_ids) == {"paladin_oath", "paladin_bulwark"}

    def test_oath_effects(self):
        perk = get_perk_config("paladin", "paladin_oath")
        assert perk is not None
        assert perk.effects.get("ontime_bonus_extra") == 0.10

    def test_bulwark_effects(self):
        perk = get_perk_config("paladin", "paladin_bulwark")
        assert perk is not None
        assert perk.effects.get("five_star_bonus_extra") == 0.10

    def test_champion_effects(self):
        perk = get_perk_config("paladin", "paladin_champion")
        assert perk is not None
        assert perk.effects.get("ontime_bonus_extra") == 0.10
        assert perk.effects.get("five_star_bonus_extra") == 0.10

    def test_champion_tier3_cost(self):
        perk = get_perk_config("paladin", "paladin_champion")
        assert perk is not None
        assert perk.perk_point_cost == 3

    def test_unlock_champion_needs_both_prereqs(self):
        champion = get_perk_config("paladin", "paladin_champion")
        assert champion is not None
        ok1, _ = can_unlock_perk(champion, class_level=7, owned_perk_ids={"paladin_oath"}, available_points=5)
        assert ok1 is False  # missing bulwark
        ok2, _ = can_unlock_perk(
            champion, class_level=7,
            owned_perk_ids={"paladin_oath", "paladin_bulwark"},
            available_points=3,
        )
        assert ok2 is True


# ────────────────────────────────────────────
# Archmage perk tree
# ────────────────────────────────────────────

class TestArchmagePerks:
    def test_archmage_has_five_perks(self):
        perks = get_class_perks("archmage")
        assert len(perks) == 5

    def test_perks_sorted_by_tier(self):
        perks = get_class_perks("archmage")
        tiers = [p.tier for p in perks]
        assert tiers == sorted(tiers)

    def test_tier1_perks(self):
        perks = get_class_perks("archmage")
        t1 = [p for p in perks if p.tier == 1]
        assert len(t1) == 2
        ids = {p.id for p in t1}
        assert "archmage_deep_study" in ids
        assert "archmage_mana_font" in ids

    def test_tier2_perks(self):
        perks = get_class_perks("archmage")
        t2 = [p for p in perks if p.tier == 2]
        assert len(t2) == 2
        ids = {p.id for p in t2}
        assert "archmage_spell_focus" in ids
        assert "archmage_rune_mastery" in ids

    def test_tier3_perk(self):
        perks = get_class_perks("archmage")
        t3 = [p for p in perks if p.tier == 3]
        assert len(t3) == 1
        assert t3[0].id == "archmage_omniscient"

    def test_perk_lookup(self):
        perk = get_perk_config("archmage", "archmage_deep_study")
        assert perk is not None
        assert perk.name_ru == "Глубокое изучение"
        assert perk.tier == 1
        assert perk.perk_point_cost == 1

    def test_spell_focus_prerequisite(self):
        perk = get_perk_config("archmage", "archmage_spell_focus")
        assert perk is not None
        assert perk.prerequisite_ids == ["archmage_deep_study"]

    def test_rune_mastery_prerequisite(self):
        perk = get_perk_config("archmage", "archmage_rune_mastery")
        assert perk is not None
        assert perk.prerequisite_ids == ["archmage_mana_font"]

    def test_omniscient_prerequisites(self):
        perk = get_perk_config("archmage", "archmage_omniscient")
        assert perk is not None
        assert set(perk.prerequisite_ids) == {"archmage_deep_study", "archmage_mana_font"}

    def test_deep_study_effects(self):
        perk = get_perk_config("archmage", "archmage_deep_study")
        assert perk is not None
        assert perk.effects.get("high_budget_bonus_extra") == 0.10

    def test_rune_mastery_effects(self):
        perk = get_perk_config("archmage", "archmage_rune_mastery")
        assert perk is not None
        assert perk.effects.get("extra_quest_slot_bonus") == 1

    def test_omniscient_effects(self):
        perk = get_perk_config("archmage", "archmage_omniscient")
        assert perk is not None
        assert perk.effects.get("high_budget_bonus_extra") == 0.15

    def test_omniscient_required_level(self):
        perk = get_perk_config("archmage", "archmage_omniscient")
        assert perk is not None
        assert perk.required_class_level == 8

    def test_omniscient_tier3_cost(self):
        perk = get_perk_config("archmage", "archmage_omniscient")
        assert perk is not None
        assert perk.perk_point_cost == 3

    def test_unlock_omniscient_needs_both_prereqs(self):
        omniscient = get_perk_config("archmage", "archmage_omniscient")
        assert omniscient is not None
        ok1, _ = can_unlock_perk(omniscient, class_level=8, owned_perk_ids={"archmage_deep_study"}, available_points=5)
        assert ok1 is False  # missing mana_font
        ok2, _ = can_unlock_perk(
            omniscient, class_level=8,
            owned_perk_ids={"archmage_deep_study", "archmage_mana_font"},
            available_points=3,
        )
        assert ok2 is True


# ────────────────────────────────────────────
# Oracle perk tree
# ────────────────────────────────────────────

class TestOraclePerks:
    def test_oracle_has_five_perks(self):
        perks = get_class_perks("oracle")
        assert len(perks) == 5

    def test_perks_sorted_by_tier(self):
        perks = get_class_perks("oracle")
        tiers = [p.tier for p in perks]
        assert tiers == sorted(tiers)

    def test_tier1_perks(self):
        perks = get_class_perks("oracle")
        t1 = [p for p in perks if p.tier == 1]
        assert len(t1) == 2
        ids = {p.id for p in t1}
        assert "oracle_third_eye" in ids
        assert "oracle_prophecy" in ids

    def test_tier2_perks(self):
        perks = get_class_perks("oracle")
        t2 = [p for p in perks if p.tier == 2]
        assert len(t2) == 2
        ids = {p.id for p in t2}
        assert "oracle_pattern_weaving" in ids
        assert "oracle_foresight" in ids

    def test_tier3_perk(self):
        perks = get_class_perks("oracle")
        t3 = [p for p in perks if p.tier == 3]
        assert len(t3) == 1
        assert t3[0].id == "oracle_omniscience"

    def test_perk_lookup(self):
        perk = get_perk_config("oracle", "oracle_third_eye")
        assert perk is not None
        assert perk.name_ru == "Третий глаз"
        assert perk.tier == 1
        assert perk.perk_point_cost == 1

    def test_pattern_weaving_prerequisite(self):
        perk = get_perk_config("oracle", "oracle_pattern_weaving")
        assert perk is not None
        assert perk.prerequisite_ids == ["oracle_third_eye"]

    def test_foresight_prerequisite(self):
        perk = get_perk_config("oracle", "oracle_foresight")
        assert perk is not None
        assert perk.prerequisite_ids == ["oracle_prophecy"]

    def test_omniscience_prerequisites(self):
        perk = get_perk_config("oracle", "oracle_omniscience")
        assert perk is not None
        assert set(perk.prerequisite_ids) == {"oracle_third_eye", "oracle_prophecy"}

    def test_third_eye_effects(self):
        perk = get_perk_config("oracle", "oracle_third_eye")
        assert perk is not None
        assert perk.effects.get("analytics_bonus_extra") == 0.10

    def test_foresight_effects(self):
        perk = get_perk_config("oracle", "oracle_foresight")
        assert perk is not None
        assert perk.effects.get("extra_quest_slot_bonus") == 1

    def test_omniscience_effects(self):
        perk = get_perk_config("oracle", "oracle_omniscience")
        assert perk is not None
        assert perk.effects.get("analytics_bonus_extra") == 0.15

    def test_omniscience_required_level(self):
        perk = get_perk_config("oracle", "oracle_omniscience")
        assert perk is not None
        assert perk.required_class_level == 9

    def test_omniscience_tier3_cost(self):
        perk = get_perk_config("oracle", "oracle_omniscience")
        assert perk is not None
        assert perk.perk_point_cost == 3

    def test_unlock_omniscience_needs_both_prereqs(self):
        omniscience = get_perk_config("oracle", "oracle_omniscience")
        assert omniscience is not None
        ok1, _ = can_unlock_perk(omniscience, class_level=9, owned_perk_ids={"oracle_third_eye"}, available_points=5)
        assert ok1 is False  # missing prophecy
        ok2, _ = can_unlock_perk(
            omniscience, class_level=9,
            owned_perk_ids={"oracle_third_eye", "oracle_prophecy"},
            available_points=3,
        )
        assert ok2 is True
