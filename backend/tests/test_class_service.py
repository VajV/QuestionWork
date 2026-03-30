"""Targeted coverage for class_service write flows."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.class_service import activate_ability, reset_class, unlock_perk


@pytest.mark.asyncio
async def test_reset_class_clears_active_class():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"character_class": "berserk"})

    with patch(
        "app.services.class_service.invalidate_cache_scope",
        new=AsyncMock(),
        create=True,
    ) as mock_invalidate:
        result = await reset_class(conn, SimpleNamespace(id="user_1"))

    assert "сброшен" in result["message"].lower()
    update_query = conn.execute.await_args.args[0]
    assert "character_class = NULL" in update_query
    mock_invalidate.assert_awaited_once_with("class_info", "user", "user_1")


@pytest.mark.asyncio
async def test_unlock_perk_spends_points_and_returns_perk_info():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"character_class": "berserk"},
            {"class_level": 2, "perk_points_spent": 0, "bonus_perk_points": 0},
        ]
    )
    conn.fetch = AsyncMock(return_value=[])

    with patch("app.services.class_service.notification_service.create_notification", new=AsyncMock()):
        result = await unlock_perk(conn, "user_1", "berserk_adrenaline")

    assert result.perk.perk_id == "berserk_adrenaline"
    assert result.perk_points_available == 0
    assert conn.execute.await_count == 2


@pytest.mark.asyncio
async def test_activate_ability_rejects_cooldown_window():
    future = datetime.now(timezone.utc) + timedelta(hours=6)
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"character_class": "berserk"},
            {"class_level": 5, "rage_active_until": None},
            {"cooldown_until": future, "active_until": None, "times_used": 1},
        ]
    )

    with pytest.raises(ValueError, match="Перезарядка"):
        await activate_ability(conn, "user_1", "rage_mode")


@pytest.mark.asyncio
async def test_activate_ability_sets_rage_state_and_returns_active_info():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"character_class": "berserk"},
            {"class_level": 5, "rage_active_until": None},
            None,
        ]
    )

    with patch("app.services.class_service.notification_service.create_notification", new=AsyncMock()):
        result = await activate_ability(conn, "user_1", "rage_mode")

    assert result.ability.ability_id == "rage_mode"
    assert result.ability.is_active is True
    assert result.ability.times_used == 1
    assert conn.execute.await_count == 2