"""Tests for message_service — quest chat, system messages and unread dialogs."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from app.services import message_service


def _make_conn():
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=True)
    return conn


def _quest_row(status="assigned", client_id="user_client", assigned_to="user_fl"):
    return {
        "client_id": client_id,
        "assigned_to": assigned_to,
        "status": status,
    }


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_creates_user_message_and_updates_read_receipt(self):
        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _quest_row(),
            {"username": "freelancer"},
        ]

        result = await message_service.send_message(conn, "quest_1", "user_fl", " Hello ")

        assert result["quest_id"] == "quest_1"
        assert result["author_id"] == "user_fl"
        assert result["message_type"] == "user"
        assert conn.execute.await_count == 2


class TestCreateSystemMessage:
    @pytest.mark.asyncio
    async def test_creates_system_message(self):
        conn = _make_conn()

        result = await message_service.create_system_message(conn, "quest_1", "System text")

        assert result["author_id"] is None
        assert result["message_type"] == "system"
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_requires_existing_transaction(self):
        conn = AsyncMock()
        conn.is_in_transaction = MagicMock(return_value=False)

        with pytest.raises(RuntimeError, match="within a transaction"):
            await message_service.create_system_message(conn, "quest_1", "System text")


class TestGetMessages:
    @pytest.mark.asyncio
    async def test_returns_messages_unread_count_and_marks_read(self):
        conn = _make_conn()
        conn.fetchrow.return_value = _quest_row()
        conn.fetchval.side_effect = [2, 3]
        conn.fetch.return_value = [
            {
                "id": "msg_1",
                "quest_id": "quest_1",
                "author_id": None,
                "author_username": None,
                "text": "Системное сообщение",
                "created_at": datetime.now(timezone.utc),
                "message_type": "system",
            },
            {
                "id": "msg_2",
                "quest_id": "quest_1",
                "author_id": "user_fl",
                "author_username": "freelancer",
                "text": "Привет",
                "created_at": datetime.now(timezone.utc),
                "message_type": "user",
            },
        ]

        result = await message_service.get_messages(conn, "quest_1", "user_client")

        assert result["total"] == 3
        assert result["unread_count"] == 2
        assert len(result["messages"]) == 2
        assert result["messages"][0]["message_type"] == "user"
        assert conn.execute.await_count == 1


class TestListDialogs:
    @pytest.mark.asyncio
    async def test_returns_dialogs_with_other_party_and_unread_count(self):
        conn = _make_conn()
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [
            {
                "quest_id": "quest_1",
                "quest_title": "Test Quest",
                "quest_status": "in_progress",
                "client_id": "user_client",
                "assigned_to": "user_fl",
                "client_username": "client",
                "freelancer_username": "freelancer",
                "last_message_text": "Контракт отправлен на проверку",
                "last_message_type": "system",
                "last_message_at": datetime.now(timezone.utc),
                "unread_count": 3,
            }
        ]

        result = await message_service.list_dialogs(conn, "user_client")

        assert result["total"] == 1
        assert len(result["dialogs"]) == 1
        assert result["dialogs"][0]["other_username"] == "freelancer"
        assert result["dialogs"][0]["unread_count"] == 3

    @pytest.mark.asyncio
    async def test_falls_back_when_read_receipt_schema_is_missing(self):
        conn = _make_conn()
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            asyncpg.UndefinedTableError('relation "quest_message_reads" does not exist'),
            [
                {
                    "quest_id": "quest_1",
                    "quest_title": "Test Quest",
                    "quest_status": "in_progress",
                    "client_id": "user_client",
                    "assigned_to": "user_fl",
                    "client_username": "client",
                    "freelancer_username": "freelancer",
                    "last_message_text": None,
                    "last_message_type": None,
                    "last_message_at": None,
                    "unread_count": 0,
                }
            ],
        ]

        result = await message_service.list_dialogs(conn, "user_client")

        assert result["total"] == 1
        assert result["dialogs"][0]["other_username"] == "freelancer"
        assert result["dialogs"][0]["last_message_type"] == "user"
        assert result["dialogs"][0]["unread_count"] == 0

    @pytest.mark.asyncio
    async def test_falls_back_on_enum_function_error(self):
        """Regression: quest_status_enum vs text comparison must not crash."""
        conn = _make_conn()
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            asyncpg.UndefinedFunctionError(
                'operator does not exist: quest_status_enum = text'
            ),
            [
                {
                    "quest_id": "quest_1",
                    "quest_title": "Test Quest",
                    "quest_status": "in_progress",
                    "client_id": "user_client",
                    "assigned_to": "user_fl",
                    "client_username": "client",
                    "freelancer_username": "freelancer",
                    "last_message_text": None,
                    "last_message_type": None,
                    "last_message_at": None,
                    "unread_count": 0,
                }
            ],
        ]

        result = await message_service.list_dialogs(conn, "user_client")

        assert result["total"] == 1
        assert result["dialogs"][0]["other_username"] == "freelancer"
