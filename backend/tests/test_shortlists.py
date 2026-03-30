"""Tests for shortlist endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone


@pytest.fixture
def shortlist_mocks():
    """Provide mock connection and auth for shortlist tests."""
    from app.models.user import UserProfile, GradeEnum, UserRoleEnum, UserStats

    client_user = UserProfile(
        id="user_client1",
        username="test_client",
        email="client@test.com",
        role=UserRoleEnum.client,
        level=3,
        grade=GradeEnum.novice,
        xp=200,
        xp_to_next=300,
        stats=UserStats(intelligence=10, dexterity=10, charisma=10),
    )

    freelancer_user = UserProfile(
        id="user_free1",
        username="test_freelancer",
        email="free@test.com",
        role=UserRoleEnum.freelancer,
        level=5,
        grade=GradeEnum.junior,
        xp=600,
        xp_to_next=1400,
        stats=UserStats(intelligence=12, dexterity=11, charisma=10),
    )

    return client_user, freelancer_user


@pytest.mark.asyncio
async def test_add_to_shortlist_service():
    """Test shortlist_service.add_to_shortlist."""
    from app.services.shortlist_service import add_to_shortlist

    now = datetime.now(timezone.utc)
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": "sl_abc123",
        "client_id": "user_client1",
        "freelancer_id": "user_free1",
        "created_at": now,
    }

    result = await add_to_shortlist(mock_conn, "user_client1", "user_free1")
    assert result["id"] == "sl_abc123"
    assert result["client_id"] == "user_client1"
    assert result["freelancer_id"] == "user_free1"


@pytest.mark.asyncio
async def test_remove_from_shortlist_service():
    """Test shortlist_service.remove_from_shortlist."""
    from app.services.shortlist_service import remove_from_shortlist

    mock_conn = AsyncMock()
    mock_conn.execute.return_value = "DELETE 1"

    result = await remove_from_shortlist(mock_conn, "user_client1", "user_free1")
    assert result is True


@pytest.mark.asyncio
async def test_remove_from_shortlist_not_found():
    """Test removal returns False when not found."""
    from app.services.shortlist_service import remove_from_shortlist

    mock_conn = AsyncMock()
    mock_conn.execute.return_value = "DELETE 0"

    result = await remove_from_shortlist(mock_conn, "user_client1", "user_nonexist")
    assert result is False


@pytest.mark.asyncio
async def test_get_shortlist_service():
    """Test shortlist_service.get_shortlist."""
    from app.services.shortlist_service import get_shortlist

    now = datetime.now(timezone.utc)
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 2
    mock_conn.fetch.return_value = [
        {"id": "sl_1", "client_id": "user_c1", "freelancer_id": "user_f1", "created_at": now},
        {"id": "sl_2", "client_id": "user_c1", "freelancer_id": "user_f2", "created_at": now},
    ]

    result = await get_shortlist(mock_conn, "user_c1")
    assert result["total"] == 2
    assert len(result["entries"]) == 2


@pytest.mark.asyncio
async def test_get_shortlisted_ids_service():
    """Test shortlist_service.get_shortlisted_ids."""
    from app.services.shortlist_service import get_shortlisted_ids

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {"freelancer_id": "user_f1"},
        {"freelancer_id": "user_f2"},
    ]

    ids = await get_shortlisted_ids(mock_conn, "user_c1")
    assert ids == ["user_f1", "user_f2"]
