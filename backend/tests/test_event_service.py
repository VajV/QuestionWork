"""Unit tests for event_service.py — mocked asyncpg connection."""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import event_service
from app.models.event import EventStatus


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_conn(in_transaction=True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_transaction)
    return conn


def _now():
    return datetime.now(timezone.utc)


def _event_row(
    status="draft",
    xp_multiplier=Decimal("1.5"),
    badge_reward_id=None,
    max_participants=None,
):
    now = _now()
    return {
        "id": "evt_test12345678",
        "title": "Test Seasonal Event",
        "description": "This is a test event with enough characters for validation.",
        "status": status,
        "xp_multiplier": xp_multiplier,
        "badge_reward_id": badge_reward_id,
        "max_participants": max_participants,
        "created_by": "admin_1",
        "start_at": now + timedelta(hours=1),
        "end_at": now + timedelta(hours=25),
        "finalized_at": None,
        "created_at": now,
        "updated_at": now,
    }


def _participant_row(event_id="evt_test12345678", user_id="user_1", score=0):
    return {
        "id": "evp_test12345678",
        "event_id": event_id,
        "user_id": user_id,
        "score": score,
        "joined_at": _now(),
        "username": "testuser",
    }


# ─────────────────────────────────────────────────────────────────────
# create_event
# ─────────────────────────────────────────────────────────────────────

class TestCreateEvent:
    @pytest.mark.asyncio
    async def test_requires_transaction(self):
        conn = _make_conn(in_transaction=False)
        now = _now()
        with pytest.raises(RuntimeError, match="transaction"):
            await event_service.create_event(
                conn,
                title="Test Event Long Enough",
                description="A description that is long enough for the validator to accept",
                xp_multiplier=Decimal("1.5"),
                badge_reward_id=None,
                max_participants=None,
                start_at=now + timedelta(hours=1),
                end_at=now + timedelta(hours=25),
                created_by="admin_1",
            )

    @pytest.mark.asyncio
    async def test_validates_dates_end_before_start(self):
        conn = _make_conn()
        now = _now()
        with pytest.raises(ValueError, match="end_at must be after start_at"):
            await event_service.create_event(
                conn,
                title="Test Event Long Enough",
                description="A description that is long enough for the validator to accept",
                xp_multiplier=Decimal("1.5"),
                badge_reward_id=None,
                max_participants=None,
                start_at=now + timedelta(hours=25),
                end_at=now + timedelta(hours=1),
                created_by="admin_1",
            )

    @pytest.mark.asyncio
    async def test_validates_duration_max_72h(self):
        conn = _make_conn()
        now = _now()
        with pytest.raises(ValueError, match="72 hours"):
            await event_service.create_event(
                conn,
                title="Test Event Long Enough",
                description="A description that is long enough for the validator to accept",
                xp_multiplier=Decimal("1.5"),
                badge_reward_id=None,
                max_participants=None,
                start_at=now + timedelta(hours=1),
                end_at=now + timedelta(hours=100),
                created_by="admin_1",
            )

    @pytest.mark.asyncio
    async def test_validates_badge_exists(self):
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=None)
        now = _now()
        with pytest.raises(ValueError, match="Badge.*not found"):
            await event_service.create_event(
                conn,
                title="Test Event Long Enough",
                description="A description that is long enough for the validator to accept",
                xp_multiplier=Decimal("1.5"),
                badge_reward_id="nonexistent_badge",
                max_participants=None,
                start_at=now + timedelta(hours=1),
                end_at=now + timedelta(hours=25),
                created_by="admin_1",
            )

    @pytest.mark.asyncio
    async def test_success_creates_draft_event(self):
        conn = _make_conn()
        now = _now()
        row = _event_row()
        conn.fetchrow = AsyncMock(return_value=row)

        result = await event_service.create_event(
            conn,
            title="Test Event Long Enough",
            description="A description that is long enough for the validator to accept",
            xp_multiplier=Decimal("1.5"),
            badge_reward_id=None,
            max_participants=None,
            start_at=now + timedelta(hours=1),
            end_at=now + timedelta(hours=25),
            created_by="admin_1",
        )

        assert result.id == "evt_test12345678"
        assert result.status == EventStatus.draft
        conn.fetchrow.assert_called_once()


# ─────────────────────────────────────────────────────────────────────
# activate_event
# ─────────────────────────────────────────────────────────────────────

class TestActivateEvent:
    @pytest.mark.asyncio
    async def test_requires_transaction(self):
        conn = _make_conn(in_transaction=False)
        with pytest.raises(RuntimeError, match="transaction"):
            await event_service.activate_event(conn, event_id="evt_1")

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found or not in draft"):
            await event_service.activate_event(conn, event_id="evt_1")

    @pytest.mark.asyncio
    async def test_success_activates(self):
        conn = _make_conn()
        row = _event_row(status="active")
        conn.fetchrow = AsyncMock(return_value=row)

        result = await event_service.activate_event(conn, event_id="evt_test12345678")
        assert result.status == EventStatus.active


# ─────────────────────────────────────────────────────────────────────
# join_event
# ─────────────────────────────────────────────────────────────────────

class TestJoinEvent:
    @pytest.mark.asyncio
    async def test_requires_transaction(self):
        conn = _make_conn(in_transaction=False)
        with pytest.raises(RuntimeError, match="transaction"):
            await event_service.join_event(conn, event_id="evt_1", user_id="user_1")

    @pytest.mark.asyncio
    async def test_event_not_found_raises(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="Event not found"):
            await event_service.join_event(conn, event_id="evt_1", user_id="user_1")

    @pytest.mark.asyncio
    async def test_event_not_active_raises(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"id": "evt_1", "status": "draft", "max_participants": None})
        with pytest.raises(ValueError, match="only join active"):
            await event_service.join_event(conn, event_id="evt_1", user_id="user_1")

    @pytest.mark.asyncio
    async def test_already_joined_raises(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"id": "evt_1", "status": "active", "max_participants": None})
        conn.fetchval = AsyncMock(return_value="evp_existing")
        with pytest.raises(ValueError, match="Already joined"):
            await event_service.join_event(conn, event_id="evt_1", user_id="user_1")

    @pytest.mark.asyncio
    async def test_max_participants_exceeded_raises(self):
        conn = _make_conn()
        # First fetchrow = event, first fetchval = no existing participant, second fetchval = count
        conn.fetchrow = AsyncMock(
            side_effect=[
                {"id": "evt_1", "status": "active", "max_participants": 10},
            ]
        )
        conn.fetchval = AsyncMock(side_effect=[None, 10])
        with pytest.raises(ValueError, match="maximum participants"):
            await event_service.join_event(conn, event_id="evt_1", user_id="user_1")

    @pytest.mark.asyncio
    async def test_success_creates_participant(self):
        conn = _make_conn()
        now = _now()
        conn.fetchrow = AsyncMock(
            side_effect=[
                {"id": "evt_1", "status": "active", "max_participants": None},
                {"id": "user_1", "username": "testuser"},
                {"id": "evp_new", "event_id": "evt_1", "user_id": "user_1", "score": 0, "joined_at": now},
            ]
        )
        conn.fetchval = AsyncMock(return_value=None)

        result = await event_service.join_event(conn, event_id="evt_1", user_id="user_1")
        assert result.event_id == "evt_1"
        assert result.user_id == "user_1"
        assert result.score == 0


# ─────────────────────────────────────────────────────────────────────
# submit_score
# ─────────────────────────────────────────────────────────────────────

class TestSubmitScore:
    @pytest.mark.asyncio
    async def test_requires_transaction(self):
        conn = _make_conn(in_transaction=False)
        with pytest.raises(RuntimeError, match="transaction"):
            await event_service.submit_score(
                conn, event_id="evt_1", user_id="user_1", score_delta=10
            )

    @pytest.mark.asyncio
    async def test_event_not_active_raises(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"id": "evt_1", "status": "ended"})
        with pytest.raises(ValueError, match="active events"):
            await event_service.submit_score(
                conn, event_id="evt_1", user_id="user_1", score_delta=10
            )

    @pytest.mark.asyncio
    async def test_not_participant_raises(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(
            side_effect=[
                {"id": "evt_1", "status": "active"},
                None,
            ]
        )
        with pytest.raises(ValueError, match="Not a participant"):
            await event_service.submit_score(
                conn, event_id="evt_1", user_id="user_1", score_delta=10
            )

    @pytest.mark.asyncio
    async def test_success_adds_score(self):
        conn = _make_conn()
        now = _now()
        conn.fetchrow = AsyncMock(
            side_effect=[
                {"id": "evt_1", "status": "active"},
                {"id": "evp_1", "event_id": "evt_1", "user_id": "user_1", "score": 50, "joined_at": now},
                {"username": "testuser"},
            ]
        )
        conn.execute = AsyncMock()

        result = await event_service.submit_score(
            conn, event_id="evt_1", user_id="user_1", score_delta=25
        )
        assert result.score == 75


# ─────────────────────────────────────────────────────────────────────
# finalize_event
# ─────────────────────────────────────────────────────────────────────

class TestFinalizeEvent:
    @pytest.mark.asyncio
    async def test_requires_transaction(self):
        conn = _make_conn(in_transaction=False)
        with pytest.raises(RuntimeError, match="transaction"):
            await event_service.finalize_event(conn, event_id="evt_1")

    @pytest.mark.asyncio
    async def test_not_ended_raises(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=_event_row(status="active"))
        with pytest.raises(ValueError, match="must be ended"):
            await event_service.finalize_event(conn, event_id="evt_1")

    @pytest.mark.asyncio
    async def test_already_finalized_returns_early(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=_event_row(status="finalized"))
        result = await event_service.finalize_event(conn, event_id="evt_1")
        assert result["already_finalized"] is True

    @pytest.mark.asyncio
    async def test_success_no_participants(self):
        conn = _make_conn()
        event = _event_row(status="ended")
        conn.fetchrow = AsyncMock(return_value=event)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()

        result = await event_service.finalize_event(conn, event_id="evt_test12345678")
        assert result["participants"] == 0
        assert result["xp_awards"] == 0


# ─────────────────────────────────────────────────────────────────────
# auto_activate / auto_end
# ─────────────────────────────────────────────────────────────────────

class TestAutoActivateEnd:
    @pytest.mark.asyncio
    async def test_auto_activate_returns_count(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="UPDATE 3")
        count = await event_service.auto_activate_due_events(conn)
        assert count == 3

    @pytest.mark.asyncio
    async def test_auto_end_returns_count(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="UPDATE 0")
        count = await event_service.auto_end_due_events(conn)
        assert count == 0


# ─────────────────────────────────────────────────────────────────────
# get_event / list_events / get_leaderboard (read operations)
# ─────────────────────────────────────────────────────────────────────

class TestReadOperations:
    @pytest.mark.asyncio
    async def test_get_event_not_found(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="Event not found"):
            await event_service.get_event(conn, "evt_nonexistent")

    @pytest.mark.asyncio
    async def test_get_event_success(self):
        conn = AsyncMock()
        row = _event_row(status="active")
        conn.fetchrow = AsyncMock(return_value=row)
        conn.fetchval = AsyncMock(return_value=5)

        result = await event_service.get_event(conn, "evt_test12345678")
        assert result.id == "evt_test12345678"
        assert result.participant_count == 5

    @pytest.mark.asyncio
    async def test_list_events_empty(self):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)

        result = await event_service.list_events(conn, limit=20, offset=0)
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_get_leaderboard_not_found(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="Event not found"):
            await event_service.get_leaderboard(conn, "evt_nonexistent")

    @pytest.mark.asyncio
    async def test_get_leaderboard_empty(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": "evt_1", "status": "active"})
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetch = AsyncMock(return_value=[])

        result = await event_service.get_leaderboard(conn, "evt_1")
        assert result.total_participants == 0
        assert result.entries == []
