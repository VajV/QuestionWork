from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import guild_progression_service


def _make_conn(in_txn: bool = True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_txn)
    return conn


def test_get_current_season_code_splits_year_halves():
    assert guild_progression_service.get_current_season_code(datetime(2026, 3, 17, tzinfo=timezone.utc)) == "2026-S1"
    assert guild_progression_service.get_current_season_code(datetime(2026, 9, 2, tzinfo=timezone.utc)) == "2026-S2"


def test_resolve_tier_uses_approved_thresholds():
    assert guild_progression_service.resolve_tier(0) == "bronze"
    assert guild_progression_service.resolve_tier(5000) == "silver"
    assert guild_progression_service.resolve_tier(20000) == "gold"
    assert guild_progression_service.resolve_tier(50000) == "platinum"


@pytest.mark.asyncio
async def test_apply_guild_xp_gain_inserts_progress_and_records_promotion():
    conn = _make_conn()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=2)

    with patch(
        "app.services.guild_progression_service.invalidate_cache_scope",
        new=AsyncMock(),
        create=True,
    ) as mock_invalidate:
        result = await guild_progression_service.apply_guild_xp_gain(
            conn,
            guild_id="guild_1",
            xp_gain=5200,
            source="quest_confirmed",
            user_id="user_1",
            quest_id="quest_1",
            occurred_at=datetime(2026, 3, 17, 9, 0, tzinfo=timezone.utc),
        )

    assert result["season_code"] == "2026-S1"
    assert result["seasonal_xp"] == 5200
    assert result["current_tier"] == "silver"
    assert result["previous_tier"] == "bronze"
    assert result["promoted"] is True
    assert result["xp_bonus_percent"] == 5
    assert result["season_rank"] == 2
    assert conn.execute.await_count == 3
    mock_invalidate.assert_awaited_once_with("guild_progress", "guild", "guild_1")


@pytest.mark.asyncio
async def test_get_guild_progress_state_returns_ranked_snapshot():
    conn = _make_conn()
    conn.fetchrow = AsyncMock(
        return_value={
            "season_code": "2026-S1",
            "seasonal_xp": 23000,
            "current_tier": "gold",
        }
    )
    conn.fetchval = AsyncMock(return_value=1)

    result = await guild_progression_service.get_guild_progress_state(conn, "guild_1", season_code="2026-S1")

    assert result["current_tier"] == "gold"
    assert result["next_tier"] == "platinum"
    assert result["next_tier_xp"] == 50000
    assert result["xp_to_next_tier"] == 27000
    assert result["season_rank"] == 1
    assert result["progress_percent"] > 0