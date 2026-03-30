"""
In-process event system for decoupled service communication.

Handlers are called within the same DB transaction (conn is passed through).
This keeps the system simple while providing loose coupling between Class Engine,
Notification Service, Badge Service, etc.

Usage:
    from app.core.events import event_bus, QuestCompleted

    # Subscribe (at module load / app startup)
    @event_bus.on(QuestCompleted)
    async def handle_quest_completed(conn, event: QuestCompleted):
        ...

    # Emit (inside a service function, within a transaction)
    await event_bus.emit(conn, QuestCompleted(user_id="u1", quest_id="q1", ...))
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Coroutine, Optional

import asyncpg

from app.models.user import GradeEnum

logger = logging.getLogger(__name__)

# Type alias for async event handler: (conn, event) -> None
EventHandler = Callable[[asyncpg.Connection, Any], Coroutine[Any, Any, None]]


class EventBus:
    """Simple in-process async event bus.

    Subscribers are keyed by event class. When an event is emitted,
    all registered handlers for that event type are called sequentially
    within the same DB transaction.
    """

    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler]] = {}

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        """Register a handler for an event type (P2-22: skip duplicates)."""
        handlers_list = self._handlers.setdefault(event_type, [])
        if handler not in handlers_list:
            handlers_list.append(handler)
            logger.debug("EventBus: subscribed %s to %s", handler.__name__, event_type.__name__)

    def on(self, event_type: type):
        """Decorator form of subscribe.

        Usage::

            @event_bus.on(QuestCompleted)
            async def my_handler(conn, event):
                ...
        """
        def decorator(handler: EventHandler) -> EventHandler:
            self.subscribe(event_type, handler)
            return handler
        return decorator

    async def emit(self, conn: asyncpg.Connection, event: Any) -> None:
        """Emit an event — call all subscribers sequentially.

        Handlers receive the asyncpg connection (same transaction) and event.
        If a handler raises, the exception propagates and the transaction
        can be rolled back by the caller.
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return
        logger.debug("EventBus: emitting %s to %d handler(s)", event_type.__name__, len(handlers))
        for handler in handlers:
            try:
                await handler(conn, event)
            except Exception:
                logger.exception(
                    "EventBus: handler %s failed for %s",
                    handler.__name__,
                    event_type.__name__,
                )
                raise

    def clear(self) -> None:
        """Remove all handlers (useful for testing)."""
        self._handlers.clear()


# ────────────────────────────────────────────
# Singleton event bus
# ────────────────────────────────────────────
event_bus = EventBus()


# ────────────────────────────────────────────
# Event dataclasses
# ────────────────────────────────────────────

@dataclass(frozen=True)
class QuestCompleted:
    """Fired when a quest is confirmed by client and rewards are distributed."""
    user_id: str
    quest_id: str
    base_xp: int
    final_xp: int
    quest_budget: Decimal  # P0-05 FIX: was `object`, now properly typed
    is_urgent: bool
    quest_grade: GradeEnum
    user_grade: GradeEnum
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class QuestTaken:
    """Fired when a freelancer is assigned to a quest."""
    user_id: str
    quest_id: str
    is_urgent: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class LevelUp:
    """Fired when a user gains a level."""
    user_id: str
    old_level: int
    new_level: int
    new_grade: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ClassLevelUp:
    """Fired when a user's class level increases."""
    user_id: str
    class_id: str
    old_level: int
    new_level: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
