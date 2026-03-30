"""Unit tests for guild_economy_service."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import guild_economy_service


def _make_conn(in_txn: bool = True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_txn)
    return conn


class TestGuildEconomyDeltas:
    def test_derives_non_zero_progression(self):
        result = guild_economy_service.derive_quest_completion_deltas(
            gross_amount=Decimal("1000.00"),
            platform_fee=Decimal("100.00"),
            xp_reward=220,
        )

        assert result["treasury_delta"] == Decimal("35.00")
        assert result["guild_tokens_delta"] >= 1
        assert result["contribution_delta"] > 220
        assert result["rating_delta"] > 0


class TestApplyQuestCompletionRewards:
    @pytest.mark.asyncio
    async def test_returns_none_when_freelancer_has_no_guild(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=None)

        result = await guild_economy_service.apply_quest_completion_rewards(
            conn,
            quest_id="quest_1",
            freelancer_id="user_fl",
            gross_amount=Decimal("1000.00"),
            platform_fee=Decimal("100.00"),
            xp_reward=200,
        )

        assert result is None
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_guild_records_activity_and_attaches_card_drop(self, monkeypatch):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(
            return_value={
                "guild_id": "guild_1",
                "role": "member",
                "guild_name": "Crimson Forge",
            }
        )
        conn.fetch = AsyncMock(
            return_value=[
                {"user_id": "user_fl"},
                {"user_id": "user_officer"},
            ]
        )
        monkeypatch.setattr(
            guild_economy_service.guild_card_service,
            "award_quest_card_drop",
            AsyncMock(
                return_value={
                    "id": "gcard_1",
                    "card_code": "storm-banner",
                    "name": "Storm Banner",
                    "rarity": "rare",
                    "family": "banner",
                    "description": "Rare reward",
                    "accent": "cyan",
                }
            ),
        )
        monkeypatch.setattr(
            guild_economy_service.guild_card_service,
            "claim_completed_seasonal_rewards",
            AsyncMock(
                return_value=[
                    {
                        "id": "gset_1",
                        "family": "banner",
                        "season_code": "forge-awakening",
                        "label": "Storm campaign reserve",
                        "accent": "cyan",
                        "treasury_bonus": Decimal("40.00"),
                        "guild_tokens_bonus": 3,
                        "badge_name": "Storm Standard",
                        "claimed_at": datetime.now(timezone.utc),
                    }
                ]
            ),
        )
        create_notification = AsyncMock()
        monkeypatch.setattr(
            guild_economy_service.notification_service,
            "create_notification",
            create_notification,
        )
        monkeypatch.setattr(
            guild_economy_service.guild_progression_service,
            "apply_guild_xp_gain",
            AsyncMock(
                return_value={
                    "season_code": "2026-S1",
                    "seasonal_xp": 220,
                    "current_tier": "bronze",
                    "next_tier": "silver",
                    "next_tier_xp": 5000,
                    "xp_to_next_tier": 4780,
                    "progress_percent": 4,
                    "xp_bonus_percent": 0,
                    "tier_benefits": ["+0% XP"],
                    "season_rank": 3,
                    "guild_id": "guild_1",
                    "xp_gain": 220,
                    "previous_tier": "bronze",
                    "promoted": False,
                }
            ),
        )
        monkeypatch.setattr(
            guild_economy_service.guild_progression_service,
            "check_and_unlock_milestones",
            AsyncMock(return_value=[]),
        )

        result = await guild_economy_service.apply_quest_completion_rewards(
            conn,
            quest_id="quest_1",
            freelancer_id="user_fl",
            gross_amount=Decimal("1000.00"),
            platform_fee=Decimal("100.00"),
            xp_reward=220,
            is_urgent=True,
            confirmed_at=datetime.now(timezone.utc),
        )

        assert result is not None
        assert result["guild_id"] == "guild_1"
        assert result["guild_name"] == "Crimson Forge"
        assert result["treasury_delta"] == Decimal("75.00")
        assert result["guild_tokens_delta"] == 6
        assert result["progression"]["seasonal_xp"] == 220
        assert result["card_drop"]["card_code"] == "storm-banner"
        assert result["seasonal_rewards"][0]["badge_name"] == "Storm Standard"
        assert conn.execute.await_count == 3
        assert create_notification.await_count == 2


# ---------------------------------------------------------------------------
# Plan 11: Solo completion regression tests
# ---------------------------------------------------------------------------


class TestAwardSoloArtifactDrop:
    """Regression tests for the solo card-drop branch (Plan 11, Task 4)."""

    @pytest.mark.asyncio
    async def test_solo_drop_delegates_to_guild_card_service(self, monkeypatch):
        """award_solo_artifact_drop must call guild_card_service.award_solo_quest_card_drop."""
        conn = _make_conn()
        fake_card = {
            "id": "pcard_abc",
            "card_code": "wanderer-seal",
            "name": "Wanderer Seal",
            "rarity": "rare",
            "family": "wanderer",
            "description": "A solo artifact",
            "accent": "slate",
            "item_category": "collectible",
        }
        mock_award = AsyncMock(return_value=fake_card)
        monkeypatch.setattr(
            guild_economy_service.guild_card_service,
            "award_solo_quest_card_drop",
            mock_award,
        )

        result = await guild_economy_service.award_solo_artifact_drop(
            conn,
            quest_id="quest_solo_1",
            freelancer_id="user_solo",
            gross_amount=Decimal("500.00"),
            platform_fee=Decimal("50.00"),
            xp_reward=100,
            is_urgent=False,
        )

        assert result is not None
        assert result["id"] == "pcard_abc"
        assert result["family"] == "wanderer"
        mock_award.assert_awaited_once()
        call_kwargs = mock_award.call_args.kwargs
        assert call_kwargs["quest_id"] == "quest_solo_1"
        assert call_kwargs["freelancer_id"] == "user_solo"

    @pytest.mark.asyncio
    async def test_solo_drop_returns_none_when_threshold_not_met(self, monkeypatch):
        """If the roll doesn't meet the threshold, award returns None."""
        conn = _make_conn()
        monkeypatch.setattr(
            guild_economy_service.guild_card_service,
            "award_solo_quest_card_drop",
            AsyncMock(return_value=None),
        )

        result = await guild_economy_service.award_solo_artifact_drop(
            conn,
            quest_id="quest_solo_2",
            freelancer_id="user_solo",
            gross_amount=Decimal("300.00"),
            platform_fee=Decimal("30.00"),
            xp_reward=80,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_guild_path_does_not_call_solo_drop(self, monkeypatch):
        """apply_quest_completion_rewards for guild members must NOT trigger solo drops."""
        conn = _make_conn()
        conn.fetchrow = AsyncMock(
            return_value={
                "guild_id": "guild_1",
                "role": "member",
                "guild_name": "Test Guild",
            }
        )
        conn.fetch = AsyncMock(return_value=[{"user_id": "user_fl"}])

        monkeypatch.setattr(
            guild_economy_service.guild_card_service,
            "award_quest_card_drop",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            guild_economy_service.guild_card_service,
            "claim_completed_seasonal_rewards",
            AsyncMock(return_value=[]),
        )
        monkeypatch.setattr(
            guild_economy_service.notification_service,
            "create_notification",
            AsyncMock(),
        )
        monkeypatch.setattr(
            guild_economy_service.guild_progression_service,
            "apply_guild_xp_gain",
            AsyncMock(
                return_value={
                    "season_code": "2026-S1",
                    "seasonal_xp": 100,
                    "current_tier": "bronze",
                    "next_tier": "silver",
                    "next_tier_xp": 5000,
                    "xp_to_next_tier": 4900,
                    "progress_percent": 2,
                    "xp_bonus_percent": 0,
                    "tier_benefits": ["+0% XP"],
                    "season_rank": 1,
                    "guild_id": "guild_1",
                    "xp_gain": 100,
                    "previous_tier": "bronze",
                    "promoted": False,
                }
            ),
        )
        monkeypatch.setattr(
            guild_economy_service.guild_progression_service,
            "check_and_unlock_milestones",
            AsyncMock(return_value=[]),
        )
        solo_mock = AsyncMock()
        monkeypatch.setattr(
            guild_economy_service.guild_card_service,
            "award_solo_quest_card_drop",
            solo_mock,
        )

        result = await guild_economy_service.apply_quest_completion_rewards(
            conn,
            quest_id="quest_guild_1",
            freelancer_id="user_fl",
            gross_amount=Decimal("1000.00"),
            platform_fee=Decimal("100.00"),
            xp_reward=200,
        )

        assert result is not None
        assert result["guild_id"] == "guild_1"
        solo_mock.assert_not_awaited()