"""Tests for the event bus system (app.core.events)."""

import asyncio
import pytest
from decimal import Decimal

from app.core.events import EventBus, QuestCompleted, QuestTaken, LevelUp, ClassLevelUp


@pytest.fixture
def bus():
    """Fresh EventBus instance per test."""
    b = EventBus()
    yield b
    b.clear()


class TestEventBus:
    def test_subscribe_and_list(self, bus: EventBus):
        handler = lambda conn, event: None  # noqa: E731
        bus.subscribe(QuestCompleted, handler)
        assert handler in bus._handlers[QuestCompleted]

    def test_on_decorator(self, bus: EventBus):
        @bus.on(QuestTaken)
        async def my_handler(conn, event):
            pass

        assert my_handler in bus._handlers[QuestTaken]

    @pytest.mark.asyncio
    async def test_emit_calls_handlers(self, bus: EventBus):
        calls = []

        @bus.on(QuestCompleted)
        async def handler(conn, event):
            calls.append(event)

        event = QuestCompleted(
            user_id="u1",
            quest_id="q1",
            base_xp=100,
            final_xp=120,
            quest_budget=Decimal("5000"),
            is_urgent=True,
            quest_grade="novice",
            user_grade="novice",
        )
        await bus.emit(None, event)  # conn=None for unit test
        assert len(calls) == 1
        assert calls[0].user_id == "u1"
        assert calls[0].is_urgent is True

    @pytest.mark.asyncio
    async def test_emit_multiple_handlers(self, bus: EventBus):
        results = []

        @bus.on(LevelUp)
        async def h1(conn, event):
            results.append("h1")

        @bus.on(LevelUp)
        async def h2(conn, event):
            results.append("h2")

        await bus.emit(None, LevelUp(user_id="u1", old_level=1, new_level=2, new_grade="junior"))
        assert results == ["h1", "h2"]

    @pytest.mark.asyncio
    async def test_emit_no_handlers(self, bus: EventBus):
        # Should not raise
        await bus.emit(None, ClassLevelUp(user_id="u1", class_id="berserk", old_level=1, new_level=2))

    def test_clear(self, bus: EventBus):
        @bus.on(QuestCompleted)
        async def handler(conn, event):
            pass

        bus.clear()
        assert len(bus._handlers) == 0


class TestEventDataclasses:
    def test_quest_completed_fields(self):
        e = QuestCompleted(
            user_id="u1", quest_id="q1", base_xp=100, final_xp=120,
            quest_budget=Decimal("5000"), is_urgent=False, quest_grade="novice", user_grade="junior",
        )
        assert e.user_id == "u1"
        assert e.base_xp == 100
        assert e.is_urgent is False

    def test_class_level_up_fields(self):
        e = ClassLevelUp(user_id="u1", class_id="berserk", old_level=2, new_level=3)
        assert e.class_id == "berserk"
        assert e.new_level == 3
