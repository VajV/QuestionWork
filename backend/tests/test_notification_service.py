"""Tests for notification_service — create, list, mark-as-read, mark-all-as-read."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.notification_service import (
    create_notification,
    get_notifications,
    mark_as_read,
    mark_all_as_read,
)
from app.models.badge_notification import Notification


# ────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────

def _make_conn(in_txn=True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_txn)
    return conn


def _notif_row(
    notif_id="notif_abc",
    user_id="user1",
    title="Hello",
    message="World",
    event_type="general",
    is_read=False,
):
    return {
        "id": notif_id,
        "user_id": user_id,
        "title": title,
        "message": message,
        "event_type": event_type,
        "is_read": is_read,
        "created_at": datetime.now(timezone.utc),
    }


# ────────────────────────────────────────────
# create_notification
# ────────────────────────────────────────────

class TestCreateNotification:
    @pytest.mark.asyncio
    async def test_creates_notification_in_transaction(self):
        conn = _make_conn()

        result = await create_notification(
            conn,
            user_id="user1",
            title="Quest Confirmed!",
            message="Your quest was confirmed.",
            event_type="quest_confirmed",
        )

        assert isinstance(result, Notification)
        assert result.user_id == "user1"
        assert result.title == "Quest Confirmed!"
        assert result.event_type == "quest_confirmed"
        assert result.is_read is False
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_defaults_event_type_to_general(self):
        conn = _make_conn()

        result = await create_notification(conn, "user1", "Hi", "Hello")

        assert result.event_type == "general"

    @pytest.mark.asyncio
    async def test_raises_if_not_in_transaction(self):
        conn = _make_conn(in_txn=False)

        with pytest.raises(RuntimeError, match="DB transaction"):
            await create_notification(conn, "user1", "Test", "Body")


# ────────────────────────────────────────────
# get_notifications
# ────────────────────────────────────────────

class TestGetNotifications:
    @pytest.mark.asyncio
    async def test_returns_notifications_for_user(self):
        conn = _make_conn(in_txn=False)
        row = _notif_row()
        conn.fetchrow = AsyncMock(return_value={"total": 1, "unread_count": 1})
        conn.fetch = AsyncMock(return_value=[row])

        result = await get_notifications(conn, "user1")

        assert result.total == 1
        assert result.unread_count == 1
        assert len(result.notifications) == 1
        assert result.notifications[0].id == row["id"]

    @pytest.mark.asyncio
    async def test_unread_only_filter(self):
        conn = _make_conn(in_txn=False)
        conn.fetchrow = AsyncMock(return_value={"total": 1})
        conn.fetch = AsyncMock(return_value=[_notif_row()])

        result = await get_notifications(conn, "user1", unread_only=True)

        # Verify query included "is_read = FALSE" in the call args
        fetch_call_args = conn.fetch.call_args
        assert "is_read = FALSE" in fetch_call_args[0][0]

    @pytest.mark.asyncio
    async def test_empty_result(self):
        conn = _make_conn(in_txn=False)
        conn.fetchrow = AsyncMock(return_value={"total": 0, "unread_count": 0})
        conn.fetch = AsyncMock(return_value=[])

        result = await get_notifications(conn, "user_empty")

        assert result.total == 0
        assert result.unread_count == 0
        assert result.notifications == []


# ────────────────────────────────────────────
# mark_as_read
# ────────────────────────────────────────────

class TestMarkAsRead:
    @pytest.mark.asyncio
    async def test_marks_owned_notification_as_read(self):
        conn = _make_conn(in_txn=True)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        updated = await mark_as_read(conn, "notif_abc", "user1")

        assert updated is True
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_if_not_found_or_not_owner(self):
        conn = _make_conn(in_txn=True)
        conn.execute = AsyncMock(return_value="UPDATE 0")

        updated = await mark_as_read(conn, "notif_xyz", "user1")

        assert updated is False

    @pytest.mark.asyncio
    async def test_returns_false_if_already_read(self):
        conn = _make_conn(in_txn=True)
        conn.execute = AsyncMock(return_value="UPDATE 0")

        updated = await mark_as_read(conn, "notif_abc", "user1")

        assert updated is False


# ────────────────────────────────────────────
# mark_all_as_read
# ────────────────────────────────────────────

class TestMarkAllAsRead:
    @pytest.mark.asyncio
    async def test_marks_all_as_read_returns_count(self):
        conn = _make_conn(in_txn=True)
        conn.execute = AsyncMock(return_value="UPDATE 5")

        count = await mark_all_as_read(conn, "user1")

        assert count == 5

    @pytest.mark.asyncio
    async def test_returns_zero_if_nothing_to_update(self):
        conn = _make_conn(in_txn=True)
        conn.execute = AsyncMock(return_value="UPDATE 0")

        count = await mark_all_as_read(conn, "user1")

        assert count == 0
