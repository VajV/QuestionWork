"""Tests for WebSocket endpoints and Redis publish helpers."""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints.ws import ws_router


class _AcquireContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_ws_app() -> FastAPI:
    app = FastAPI()
    app.include_router(ws_router)
    return app


# ─────────────────────────────────────────────────────────────────────
# WS auth — /ws/notifications
# ─────────────────────────────────────────────────────────────────────

class TestWsNotificationsAuth:
    def test_ticket_auth_connects(self):
        """First-frame ticket auth should allow the notifications socket."""
        app = _make_ws_app()

        with patch("app.api.v1.endpoints.ws.realtime_service.consume_ws_ticket",
                   new=AsyncMock(return_value={"user_id": "user_1", "scope": "notifications"})), \
             patch("app.api.v1.endpoints.ws._is_user_banned",
                   new=AsyncMock(return_value=False)), \
             patch("app.api.v1.endpoints.ws._pubsub_loop",
                   new=AsyncMock(return_value=None)):
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws/notifications") as ws:
                ws.send_json({"type": "auth", "ticket": "ticket_1"})

    def test_invalid_ticket_via_frame_closes_4001(self):
        """Garbage ticket → WS should be closed with code 4001."""
        app = _make_ws_app()

        with patch("app.api.v1.endpoints.ws.realtime_service.consume_ws_ticket",
                   new=AsyncMock(return_value=None)):
            client = TestClient(app, raise_server_exceptions=False)
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/notifications") as ws:
                    ws.send_json({"type": "auth", "ticket": "bad_token"})
                    ws.receive_text()

    def test_invalid_ticket_closes_4001(self):
        """Unknown ticket should be rejected after the first auth frame."""
        app = _make_ws_app()

        with patch("app.api.v1.endpoints.ws.realtime_service.consume_ws_ticket",
                   new=AsyncMock(return_value=None)):
            client = TestClient(app, raise_server_exceptions=False)
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/notifications") as ws:
                    ws.send_json({"type": "auth", "ticket": "missing"})
                    ws.receive_text()

    def test_valid_ticket_banned_user_closes_4003(self):
        """Banned user → WS should be closed with code 4003."""
        app = _make_ws_app()

        with patch("app.api.v1.endpoints.ws.realtime_service.consume_ws_ticket",
                   new=AsyncMock(return_value={"user_id": "user_banned", "scope": "notifications"})), \
             patch("app.api.v1.endpoints.ws._is_user_banned",
                   new=AsyncMock(return_value=True)):
            client = TestClient(app, raise_server_exceptions=False)
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/notifications") as ws:
                    ws.send_json({"type": "auth", "ticket": "valid_ticket"})
                    ws.receive_text()


# ─────────────────────────────────────────────────────────────────────
# WS auth — /ws/chat/{quest_id}
# ─────────────────────────────────────────────────────────────────────

class TestWsChatAuth:
    def test_ticket_auth_connects_for_participant(self):
        app = _make_ws_app()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"client_id": "user_1", "assigned_to": "user_2"})
        pool = MagicMock()
        pool.acquire.return_value = _AcquireContext(conn)

        with patch("app.api.v1.endpoints.ws.realtime_service.consume_ws_ticket",
                   new=AsyncMock(return_value={"user_id": "user_1", "scope": "chat", "quest_id": "quest_1"})), \
             patch("app.api.v1.endpoints.ws._is_user_banned",
                   new=AsyncMock(return_value=False)), \
             patch("app.api.v1.endpoints.ws.get_db_pool", return_value=pool), \
             patch("app.api.v1.endpoints.ws._pubsub_loop",
                   new=AsyncMock(return_value=None)):
            client = TestClient(app, raise_server_exceptions=False)
            with client.websocket_connect("/ws/chat/quest_1") as ws:
                ws.send_json({"type": "auth", "ticket": "ticket_quest"})

    def test_invalid_ticket_closes_4001(self):
        app = _make_ws_app()

        with patch("app.api.v1.endpoints.ws.realtime_service.consume_ws_ticket",
                   new=AsyncMock(return_value=None)):
            client = TestClient(app, raise_server_exceptions=False)
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/chat/quest_1") as ws:
                    ws.send_json({"type": "auth", "ticket": "bad"})
                    ws.receive_text()


# ─────────────────────────────────────────────────────────────────────
# Redis publish — notification_service
# ─────────────────────────────────────────────────────────────────────

class TestNotificationRedisPublish:
    @pytest.mark.asyncio
    async def test_create_notification_schedules_redis_publish(self):
        """create_notification should call redis.publish via asyncio.create_task."""
        from app.services import notification_service

        conn = AsyncMock()
        conn.is_in_transaction = MagicMock(return_value=True)
        conn.execute = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        published_payloads: list[str] = []

        async def fake_publish(channel: str, data: str) -> int:
            published_payloads.append(data)
            return 1

        mock_redis.publish.side_effect = fake_publish

        with patch("app.services.notification_service.get_redis_client",
                   new=AsyncMock(return_value=mock_redis)):
            result = await notification_service.create_notification(
                conn,
                user_id="user_1",
                title="Test",
                message="Hello",
                event_type="test",
            )

            # Allow the fire-and-forget task to execute
            await asyncio.sleep(0)

        assert result.id.startswith("notif_")
        assert result.title == "Test"
        # Redis publish should have been called
        assert mock_redis.publish.call_count >= 1
        channel = mock_redis.publish.call_args[0][0]
        assert channel == "notifications:user_1"

    @pytest.mark.asyncio
    async def test_create_notification_succeeds_even_if_redis_unavailable(self):
        """Redis failure must NOT break the notification creation flow."""
        from app.services import notification_service

        conn = AsyncMock()
        conn.is_in_transaction = MagicMock(return_value=True)
        conn.execute = AsyncMock()

        with patch("app.services.notification_service.get_redis_client",
                   new=AsyncMock(return_value=None)):
            result = await notification_service.create_notification(
                conn,
                user_id="user_2",
                title="Fallback test",
                message="No redis",
                event_type="general",
            )

        assert result.id.startswith("notif_")


# ─────────────────────────────────────────────────────────────────────
# Redis publish — message_service
# ─────────────────────────────────────────────────────────────────────

class TestMessageRedisPublish:
    @pytest.mark.asyncio
    async def test_send_message_schedules_redis_publish(self):
        """send_message should call redis.publish with chat:{quest_id} channel."""
        from app.services import message_service

        conn = AsyncMock()
        conn.is_in_transaction = MagicMock(return_value=True)
        conn.fetchrow = AsyncMock(side_effect=[
            # Quest row
            {"client_id": "client_1", "assigned_to": "user_1", "status": "in_progress"},
            # Author username
            {"username": "testuser"},
        ])
        conn.execute = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        with patch("app.services.message_service.get_redis_client",
                   new=AsyncMock(return_value=mock_redis)):
            result = await message_service.send_message(
                conn,
                quest_id="quest_1",
                author_id="user_1",
                text="Hello quest!",
            )

            # Allow fire-and-forget task
            await asyncio.sleep(0)

        assert result["id"].startswith("msg_")
        assert result["text"] == "Hello quest!"
        assert mock_redis.publish.call_count >= 1
        channel = mock_redis.publish.call_args[0][0]
        assert channel == "chat:quest_1"

    @pytest.mark.asyncio
    async def test_send_message_succeeds_even_if_redis_unavailable(self):
        """Redis failure must NOT break message sending."""
        from app.services import message_service

        conn = AsyncMock()
        conn.is_in_transaction = MagicMock(return_value=True)
        conn.fetchrow = AsyncMock(side_effect=[
            {"client_id": "client_1", "assigned_to": "user_1", "status": "in_progress"},
            {"username": "testuser"},
        ])
        conn.execute = AsyncMock()

        with patch("app.services.message_service.get_redis_client",
                   new=AsyncMock(return_value=None)):
            result = await message_service.send_message(
                conn,
                quest_id="quest_1",
                author_id="user_1",
                text="No redis message",
            )

        assert result["id"].startswith("msg_")


# ─────────────────────────────────────────────────────────────────────
# Redis publish payload shape
# ─────────────────────────────────────────────────────────────────────

class TestPublishPayloadShape:
    @pytest.mark.asyncio
    async def test_notification_payload_is_valid_json(self):
        """Notification publish payload must deserialise to expected fields."""
        from app.services import notification_service

        conn = AsyncMock()
        conn.is_in_transaction = MagicMock(return_value=True)
        conn.execute = AsyncMock()

        captured: list[str] = []

        async def fake_publish(channel: str, data: str) -> int:
            captured.append(data)
            return 1

        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = fake_publish

        with patch("app.services.notification_service.get_redis_client",
                   new=AsyncMock(return_value=mock_redis)):
            await notification_service.create_notification(
                conn,
                user_id="user_3",
                title="Shape test",
                message="Checking payload",
                event_type="badge_earned",
            )
            await asyncio.sleep(0)

        assert len(captured) == 1
        payload = json.loads(captured[0])
        assert "id" in payload
        assert payload["user_id"] == "user_3"
        assert payload["title"] == "Shape test"
        assert payload["event_type"] == "badge_earned"
        assert payload["is_read"] is False
        assert "created_at" in payload

    @pytest.mark.asyncio
    async def test_message_payload_is_valid_json(self):
        """Message publish payload must deserialise to expected fields."""
        from app.services import message_service

        conn = AsyncMock()
        conn.is_in_transaction = MagicMock(return_value=True)
        conn.fetchrow = AsyncMock(side_effect=[
            {"client_id": "c1", "assigned_to": "u1", "status": "in_progress"},
            {"username": "alice"},
        ])
        conn.execute = AsyncMock()

        captured: list[str] = []

        async def fake_publish(channel: str, data: str) -> int:
            captured.append(data)
            return 1

        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = fake_publish

        with patch("app.services.message_service.get_redis_client",
                   new=AsyncMock(return_value=mock_redis)):
            await message_service.send_message(conn, "q1", "u1", "Payload check")
            await asyncio.sleep(0)

        assert len(captured) == 1
        payload = json.loads(captured[0])
        assert "id" in payload
        assert payload["quest_id"] == "q1"
        assert payload["author_id"] == "u1"
        assert payload["author_username"] == "alice"
        assert payload["message_type"] == "user"
