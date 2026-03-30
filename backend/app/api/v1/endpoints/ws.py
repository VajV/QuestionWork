"""WebSocket endpoints for real-time notifications and quest chat.

Auth: first-frame JSON ticket auth (ticket obtained via REST endpoint).
Channels:
  notifications:{user_id}  — per-user notification push
  chat:{quest_id}          — per-quest chat message push
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.redis_client import get_redis_client
from app.core.ws_manager import ws_manager
from app.db.session import get_db_pool
from app.services import realtime_service

logger = logging.getLogger(__name__)

ws_router = APIRouter()
WS_AUTH_TIMEOUT_SECONDS = 5
WS_CLOSE_UNAUTHORIZED = 4001
WS_CLOSE_FORBIDDEN = 4003


# ─────────────────────────────────────────────
# Auth helper
# ─────────────────────────────────────────────

async def _close_unauthorized(ws: WebSocket) -> None:
    try:
        await ws.close(WS_CLOSE_UNAUTHORIZED)
    except RuntimeError:
        pass


async def _auth_ws(
    ws: WebSocket,
    *,
    expected_scope: str,
    quest_id: Optional[str] = None,
) -> Optional[str]:
    """Validate first-frame ticket auth and return user_id."""
    await ws.accept()

    try:
        frame = await asyncio.wait_for(ws.receive_json(), timeout=WS_AUTH_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, WebSocketDisconnect, json.JSONDecodeError, ValueError, TypeError):
        await _close_unauthorized(ws)
        return None
    except Exception:
        await _close_unauthorized(ws)
        return None

    if not isinstance(frame, dict) or frame.get("type") != "auth":
        await _close_unauthorized(ws)
        return None

    ticket = frame.get("ticket")
    if not isinstance(ticket, str) or not ticket:
        await _close_unauthorized(ws)
        return None

    payload = await realtime_service.consume_ws_ticket(
        ticket,
        expected_scope=expected_scope,
        expected_quest_id=quest_id,
    )
    if not payload or "user_id" not in payload:
        await _close_unauthorized(ws)
        return None

    return payload["user_id"]


async def _is_user_banned(user_id: str) -> bool:
    """Quick DB check — returns True if user is banned or not found."""
    try:
        db_pool = get_db_pool()
        async with db_pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT is_banned FROM users WHERE id = $1",
                user_id,
            )
            return bool(result) if result is not None else True
    except Exception:
        logger.warning("Failed to check ban status for WS user %s — denying access (fail-closed)", user_id)
        return True  # fail-closed: deny access when we cannot verify ban status


# ─────────────────────────────────────────────
# PubSub listener loop
# ─────────────────────────────────────────────

async def _pubsub_loop(ws: WebSocket, channel: str) -> None:
    """Subscribe to *channel* and forward messages to *ws* until disconnect."""
    redis = await get_redis_client()
    if redis is None:
        # Redis unavailable — just keep the WS open (client will fall back to polling)
        logger.debug("Redis unavailable; WS %s will idle (no push)", channel)
        try:
            while True:
                await asyncio.sleep(30)
        except (WebSocketDisconnect, asyncio.CancelledError):
            return

    ps = redis.pubsub()
    try:
        await ps.subscribe(channel)
        while True:
            msg = await ps.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if msg is not None and msg.get("data"):
                try:
                    await ws.send_text(msg["data"])
                except WebSocketDisconnect:
                    break
                except Exception as exc:
                    logger.debug("WS send error on %s: %s", channel, exc)
                    break
            else:
                # Yield to the event loop and check for disconnect
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("PubSub loop error on channel %s: %s", channel, exc)
    finally:
        try:
            await ps.unsubscribe(channel)
            await ps.aclose()
        except Exception:
            pass


# ─────────────────────────────────────────────
# /ws/notifications
# ─────────────────────────────────────────────

@ws_router.websocket("/ws/notifications")
async def ws_notifications(ws: WebSocket) -> None:
    """Real-time notification stream for the authenticated user.

    Connect: ws://<host>/ws/notifications
    First frame: {"type":"auth","ticket":"..."}
    Messages: JSON-encoded Notification objects pushed on creation.
    """
    user_id = await _auth_ws(ws, expected_scope="notifications")
    if user_id is None:
        return

    if await _is_user_banned(user_id):
        await ws.close(WS_CLOSE_FORBIDDEN)
        return

    await ws_manager.connect(ws, user_id, accept=False)
    try:
        await _pubsub_loop(ws, f"notifications:{user_id}")
    finally:
        ws_manager.disconnect(ws, user_id)


# ─────────────────────────────────────────────
# /ws/chat/{quest_id}
# ─────────────────────────────────────────────

@ws_router.websocket("/ws/chat/{quest_id}")
async def ws_chat(ws: WebSocket, quest_id: str) -> None:
    """Real-time chat stream for a quest.

    Connect: ws://<host>/ws/chat/<quest_id>
    First frame: {"type":"auth","ticket":"..."}
    Messages: JSON-encoded QuestMessage objects pushed on send.
    Only quest participants (client + assigned freelancer) may connect.
    """
    user_id = await _auth_ws(ws, expected_scope="chat", quest_id=quest_id)
    if user_id is None:
        return

    if await _is_user_banned(user_id):
        await ws.close(WS_CLOSE_FORBIDDEN)
        return

    # Verify user is a participant in this quest
    try:
        db_pool = get_db_pool()
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT client_id, assigned_to FROM quests WHERE id = $1",
                quest_id,
            )
    except Exception:
        logger.warning("Failed to verify quest participant for quest %s", quest_id)
        await ws.close(WS_CLOSE_FORBIDDEN)
        return

    if row is None or user_id not in (row["client_id"], row["assigned_to"]):
        await ws.close(WS_CLOSE_FORBIDDEN)
        return

    chat_key = f"chat:{quest_id}"
    await ws_manager.connect(ws, chat_key, accept=False)
    try:
        await _pubsub_loop(ws, f"chat:{quest_id}")
    finally:
        ws_manager.disconnect(ws, chat_key)
