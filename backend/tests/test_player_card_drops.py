"""Tests for Plan 11 — solo player card drops via player_card_drops table."""

from decimal import Decimal
from typing import Any

import pytest

from app.services import guild_card_service


class _Conn:
    def __init__(self, existing=None):
        self.existing = existing
        self.execute_calls: list[Any] = []
        self.fetch_rows: list[Any] = []
        self.fetchrow_rows: list[Any] = []

    async def fetchrow(self, *args, **kwargs):
        if self.fetchrow_rows:
            return self.fetchrow_rows.pop(0)
        return self.existing

    async def fetch(self, *args, **kwargs):
        if self.fetch_rows:
            return self.fetch_rows.pop(0)
        return []

    async def execute(self, *args, **kwargs):
        self.execute_calls.append((args, kwargs))
        return "INSERT 0 1"


# ---------------------------------------------------------------------------
# award_solo_quest_card_drop — persistence target
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_award_solo_writes_to_player_card_drops_not_guild_reward_cards(monkeypatch):
    """Confirmed: solo drops go to player_card_drops, never to guild_reward_cards."""
    conn = _Conn(existing=None)
    monkeypatch.setattr(
        guild_card_service,
        "roll_solo_quest_card_drop",
        lambda **_: {
            "card_code": "wanderer-seal",
            "name": "Wanderer's Seal",
            "rarity": "rare",
            "family": "wanderer",
            "description": "Solo drop test",
            "accent": "teal",
            "item_category": "collectible",
        },
    )

    result = await guild_card_service.award_solo_quest_card_drop(
        conn,
        quest_id="plan11_new_quest",
        freelancer_id="user_solo_p11",
        gross_amount=Decimal("1200.00"),
        xp_reward=150,
        is_urgent=False,
    )

    assert result is not None
    assert result["card_code"] == "wanderer-seal"
    assert result["rarity"] == "rare"
    assert result["item_category"] == "collectible"
    assert len(conn.execute_calls) == 1
    sql = conn.execute_calls[0][0][0]
    assert "player_card_drops" in sql
    assert "guild_reward_cards" not in sql


@pytest.mark.asyncio
async def test_award_solo_id_prefix_is_pcard(monkeypatch):
    """Solo card IDs must use the 'pcard_' prefix, not 'gcard_'."""
    conn = _Conn(existing=None)
    monkeypatch.setattr(
        guild_card_service,
        "roll_solo_quest_card_drop",
        lambda **_: {
            "card_code": "lone-cipher",
            "name": "Lone Cipher",
            "rarity": "rare",
            "family": "cipher",
            "description": "Cipher test",
            "accent": "indigo",
            "item_category": "collectible",
        },
    )

    result = await guild_card_service.award_solo_quest_card_drop(
        conn,
        quest_id="plan11_prefix_quest",
        freelancer_id="user_prefix",
        gross_amount=Decimal("800.00"),
        xp_reward=100,
        is_urgent=False,
    )

    assert result is not None
    assert result["id"].startswith("pcard_"), (
        f"Expected solo card ID to start with 'pcard_', got '{result['id']}'"
    )


@pytest.mark.asyncio
async def test_award_solo_returns_none_when_no_drop(monkeypatch):
    """If the roll threshold is not met, award function returns None without inserting."""
    conn = _Conn(existing=None)
    monkeypatch.setattr(
        guild_card_service,
        "roll_solo_quest_card_drop",
        lambda **_: None,  # simulated no-drop
    )

    result = await guild_card_service.award_solo_quest_card_drop(
        conn,
        quest_id="plan11_nodrop_quest",
        freelancer_id="user_nodrop",
        gross_amount=Decimal("100.00"),
        xp_reward=10,
        is_urgent=False,
    )

    assert result is None
    assert conn.execute_calls == []


@pytest.mark.asyncio
async def test_award_solo_idempotent_by_quest_id():
    """If a record already exists for quest_id, no second INSERT is made."""
    existing = {
        "id": "pcard_existing_1",
        "card_code": "drifter-crest",
        "name": "Drifter's Crest",
        "rarity": "epic",
        "family": "crest",
        "description": "Existing crest",
        "accent": "rose",
        "item_category": "cosmetic",
    }
    conn = _Conn(existing=existing)

    result = await guild_card_service.award_solo_quest_card_drop(
        conn,
        quest_id="plan11_repeat_quest",
        freelancer_id="user_repeat",
        gross_amount=Decimal("2000.00"),
        xp_reward=300,
        is_urgent=True,
    )

    assert result is not None
    assert result["id"] == "pcard_existing_1"
    assert result["rarity"] == "epic"
    assert conn.execute_calls == []  # no INSERT for duplicate quest


# ---------------------------------------------------------------------------
# Solo pool rarity distribution
# ---------------------------------------------------------------------------

def test_solo_rarity_never_common_in_large_batch():
    """Confirm the rarity floor guarantee from roll_solo_quest_card_drop."""
    drops_seen = []
    for i in range(300):
        result = guild_card_service.roll_solo_quest_card_drop(
            quest_id=f"pcd_rarity_{i}",
            freelancer_id="user_rarity_check",
            gross_amount=Decimal("2500.00"),
            xp_reward=400,
            is_urgent=True,
        )
        if result is not None:
            drops_seen.append(result["rarity"])

    assert drops_seen, "Expected at least one solo drop in 300 rolls with high params"
    assert "common" not in drops_seen, (
        f"Solo drops must never be common; found rarities: {set(drops_seen)}"
    )


def test_solo_pool_families_never_overlap_guild_families():
    """No solo card family should exist in the guild SEASONAL_FAMILY_SETS."""
    guild_families = set(guild_card_service.SEASONAL_FAMILY_SETS.keys())
    for rarity, cards in guild_card_service.SOLO_CARD_POOLS.items():
        for card in cards:
            assert card["family"] not in guild_families, (
                f"Solo card family '{card['family']}' ({rarity}) appears in guild sets"
            )


# ---------------------------------------------------------------------------
# Drop rate comparison (rate constants)
# ---------------------------------------------------------------------------

def test_solo_base_chance_is_half_of_guild():
    """SOLO_DROP_BASE_CHANCE must be exactly half of GUILD_DROP_BASE_CHANCE."""
    assert guild_card_service.SOLO_DROP_BASE_CHANCE * 2 == guild_card_service.GUILD_DROP_BASE_CHANCE


def test_drop_threshold_guild_always_exceeds_solo_at_equal_quality():
    """_drop_threshold with drop_track='guild' must return a higher value than 'solo'."""
    from decimal import Decimal as D

    for gross, xp, urgent in [
        (D("500.00"), 50, False),
        (D("2000.00"), 300, True),
        (D("100.00"), 0, False),
    ]:
        guild_t = guild_card_service._drop_threshold(gross, xp, is_urgent=urgent, drop_track="guild")
        solo_t = guild_card_service._drop_threshold(gross, xp, is_urgent=urgent, drop_track="solo")
        assert guild_t > solo_t, (
            f"Guild threshold {guild_t} should exceed solo {solo_t} "
            f"at gross={gross}, xp={xp}, urgent={urgent}"
        )
