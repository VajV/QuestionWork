from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from unittest.mock import patch

import pytest


class _Tx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _market_conn(fetchrow_side_effect, fetchval_return=0):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value=fetchval_return)
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.transaction = lambda: _Tx()
    return conn


@pytest.mark.asyncio
async def test_get_talent_market_returns_budget_availability_and_response_hints():
    from app.services.marketplace_service import get_talent_market

    conn = AsyncMock()
    conn.fetch.side_effect = [
        [],
        [
            {
                "id": "user_freelancer_1",
                "username": "market_mage",
                "level": 12,
                "grade": "middle",
                "xp": 3200,
                "xp_to_next": 1800,
                "stats_int": 18,
                "stats_dex": 14,
                "stats_cha": 11,
                "badges": [{"id": "b1"}],
                "skills": ["FastAPI", "PostgreSQL"],
                "avg_rating": Decimal("4.80"),
                "review_count": 7,
                "trust_score": Decimal("0.8123"),
                "availability_status": "limited",
                "character_class": "berserk",
                "portfolio_summary": "Strong backend cases",
                "guild_role": None,
                "guild_id": None,
                "guild_name": None,
                "guild_slug": None,
                "confirmed_quest_count": 9,
                "active_quest_count": 0,
                "avg_budget": Decimal("42000.00"),
            }
        ],
    ]
    conn.fetchrow.return_value = {
        "total_freelancers": 1,
        "solo_freelancers": 1,
        "guild_freelancers": 0,
        "top_solo_xp": 3200,
        "total_guilds": 0,
    }

    result = await get_talent_market(conn, mode="all", limit=20, offset=0)

    assert result["members"][0]["typical_budget_band"] == "15k_to_50k"
    assert result["members"][0]["availability_status"] == "limited"
    assert result["members"][0]["response_time_hint"] == "Обычно отвечает в течение рабочего дня"
    assert result["members"][0]["trust_score"] == pytest.approx(0.8123)
    assert "Высокий рейтинг" in result["members"][0]["rank_signals"]


@pytest.mark.asyncio
async def test_get_talent_market_uses_trust_sort_order_clause():
    from app.services.marketplace_service import get_talent_market

    conn = AsyncMock()
    conn.fetch.side_effect = [[], []]
    conn.fetchrow.return_value = {
        "total_freelancers": 0,
        "solo_freelancers": 0,
        "guild_freelancers": 0,
        "top_solo_xp": 0,
        "total_guilds": 0,
    }

    await get_talent_market(conn, mode="all", limit=20, offset=0, sort_by="trust")

    member_query = conn.fetch.await_args_list[1].args[0]
    assert "COALESCE(u.trust_score, -1) DESC" in member_query
    assert "u.xp DESC" in member_query


@pytest.mark.asyncio
async def test_get_talent_market_default_xp_sort_uses_trust_tie_breaker():
    from app.services.marketplace_service import get_talent_market

    conn = AsyncMock()
    conn.fetch.side_effect = [[], []]
    conn.fetchrow.return_value = {
        "total_freelancers": 0,
        "solo_freelancers": 0,
        "guild_freelancers": 0,
        "top_solo_xp": 0,
        "total_guilds": 0,
    }

    await get_talent_market(conn, mode="all", limit=20, offset=0)

    member_query = conn.fetch.await_args_list[1].args[0]
    assert "u.xp DESC, u.level DESC, COALESCE(u.trust_score, -1) DESC, u.created_at DESC" in member_query


@pytest.mark.asyncio
async def test_create_guild_invalidates_scoped_slug_cache():
    from app.services.marketplace_service import create_guild

    conn = _market_conn([None, None])
    current_user = SimpleNamespace(role="freelancer", id="user_1", username="market_mage")
    body = SimpleNamespace(name="Guild One", description="desc", emblem="sun")

    with patch(
        "app.services.marketplace_service.guild_economy_service.record_guild_activity",
        new=AsyncMock(),
    ):
        with patch(
            "app.services.marketplace_service.invalidate_cache_scope",
            new=AsyncMock(),
            create=True,
        ) as mock_invalidate:
            result = await create_guild(conn, current_user, body)

    assert result["status"] == "created"
    mock_invalidate.assert_awaited_once_with("guild_card", "slug", "guild-one")


@pytest.mark.asyncio
async def test_join_guild_invalidates_scoped_slug_cache():
    from app.services.marketplace_service import join_guild

    conn = _market_conn([None, {"id": "guild_1", "member_limit": 20, "slug": "guild-one"}])
    current_user = SimpleNamespace(role="freelancer", id="user_1", username="market_mage")

    with patch(
        "app.services.marketplace_service.guild_economy_service.record_guild_activity",
        new=AsyncMock(),
    ):
        with patch(
            "app.services.marketplace_service.invalidate_cache_scope",
            new=AsyncMock(),
            create=True,
        ) as mock_invalidate:
            result = await join_guild(conn, "guild_1", current_user)

    assert result["status"] == "joined"
    mock_invalidate.assert_awaited_once_with("guild_card", "slug", "guild-one")
