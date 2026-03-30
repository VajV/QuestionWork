from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from collections import OrderedDict
from typing import Optional

import asyncpg

from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

WS_TICKET_TTL_SECONDS = 60
_WS_TICKET_PREFIX = "ws_ticket:"
_IN_MEMORY_TICKETS: OrderedDict[str, dict] = OrderedDict()
_IN_MEMORY_MAX_TICKETS = 5000
_ticket_lock = asyncio.Lock()


def _supports_memory_ticket_fallback() -> bool:
    return True


async def _store_ticket_in_memory(ticket: str, payload: dict) -> None:
    async with _ticket_lock:
        now = time.time()
        expired = [
            key for key, value in _IN_MEMORY_TICKETS.items()
            if float(value.get("expires_at", 0)) <= now
        ]
        for key in expired:
            _IN_MEMORY_TICKETS.pop(key, None)

        while len(_IN_MEMORY_TICKETS) >= _IN_MEMORY_MAX_TICKETS:
            _IN_MEMORY_TICKETS.popitem(last=False)

        _IN_MEMORY_TICKETS[ticket] = payload


async def _consume_ticket_from_memory(ticket: str) -> Optional[dict]:
    async with _ticket_lock:
        payload = _IN_MEMORY_TICKETS.pop(ticket, None)
        if not payload:
            return None
        if float(payload.get("expires_at", 0)) <= time.time():
            return None
        return payload


async def issue_ws_ticket(*, scope: str, user_id: str, quest_id: Optional[str] = None) -> dict:
    now = int(time.time())
    ticket = secrets.token_urlsafe(32)
    payload = {
        "scope": scope,
        "user_id": user_id,
        "quest_id": quest_id,
        "issued_at": now,
        "expires_at": now + WS_TICKET_TTL_SECONDS,
    }

    redis = await get_redis_client(required_in_production=False)
    if redis is not None:
        await redis.setex(f"{_WS_TICKET_PREFIX}{ticket}", WS_TICKET_TTL_SECONDS, json.dumps(payload))
    elif _supports_memory_ticket_fallback():
        await _store_ticket_in_memory(ticket, payload)
    else:
        raise RuntimeError("WebSocket ticket storage is unavailable")

    return {
        "ticket": ticket,
        "expires_in_seconds": WS_TICKET_TTL_SECONDS,
    }


async def consume_ws_ticket(
    ticket: str,
    *,
    expected_scope: str,
    expected_quest_id: Optional[str] = None,
) -> Optional[dict]:
    if not ticket:
        return None

    payload: Optional[dict] = None
    redis = await get_redis_client(required_in_production=False)
    if redis is not None:
        key = f"{_WS_TICKET_PREFIX}{ticket}"
        try:
            pipe = redis.pipeline(True)
            pipe.get(key)
            pipe.delete(key)
            result = await pipe.execute()
            raw_payload = result[0]
        except Exception:
            logger.warning("Failed to consume WebSocket ticket from Redis", exc_info=True)
            raw_payload = None

        if raw_payload:
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                return None
    else:
        payload = await _consume_ticket_from_memory(ticket)

    if not payload:
        return None
    if payload.get("scope") != expected_scope:
        return None
    if expected_scope == "chat" and payload.get("quest_id") != expected_quest_id:
        return None
    if float(payload.get("expires_at", 0)) <= time.time():
        return None
    return payload


async def issue_notifications_ticket(user_id: str) -> dict:
    return await issue_ws_ticket(scope="notifications", user_id=user_id)


async def issue_chat_ticket(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    quest_id: str,
) -> dict:
    quest = await conn.fetchrow(
        "SELECT client_id, assigned_to FROM quests WHERE id = $1",
        quest_id,
    )
    if not quest:
        raise ValueError("Квест не найден")

    if user_id not in (quest["client_id"], quest["assigned_to"]):
        raise ValueError("Только участники квеста могут подключаться к чату")

    return await issue_ws_ticket(scope="chat", user_id=user_id, quest_id=quest_id)
