"""HTTP-level tests for event endpoints — mocked service layer."""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.api.v1.endpoints.events import router, admin_events_router
from app.models.event import EventOut, EventListResponse, EventParticipantOut, EventLeaderboardResponse, EventStatus
from app.models.user import UserProfile


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(admin_events_router, prefix="/api/v1")
    return app


def _now():
    return datetime.now(timezone.utc)


def _fake_user(role="freelancer", user_id="user_1"):
    return UserProfile(
        id=user_id,
        username="testuser",
        email="test@example.com",
        role=role,
        grade="junior",
        level=5,
        xp=500,
        xp_to_next=200,
        stats={"int": 10, "dex": 10, "cha": 10},
        badges=[],
        is_banned=False,
    )


def _event_out(status="active"):
    now = _now()
    return EventOut(
        id="evt_test12345678",
        title="Test Event",
        description="A seasonal event for testing purposes",
        status=EventStatus(status),
        xp_multiplier=Decimal("1.5"),
        badge_reward_id=None,
        max_participants=100,
        participant_count=5,
        created_by="admin_1",
        start_at=now,
        end_at=now + timedelta(hours=24),
        finalized_at=None,
        created_at=now,
        updated_at=now,
    )


def _event_list_response():
    return EventListResponse(items=[_event_out()], total=1, has_more=False)


def _participant_out():
    return EventParticipantOut(
        id="evp_test12345678",
        event_id="evt_test12345678",
        user_id="user_1",
        username="testuser",
        score=0,
        joined_at=_now(),
    )


def _leaderboard_response():
    return EventLeaderboardResponse(
        event_id="evt_test12345678",
        entries=[],
        total_participants=0,
    )


# ─────────────────────────────────────────────────────────────────────
# Public endpoints
# ─────────────────────────────────────────────────────────────────────

class TestListEvents:
    @pytest.mark.asyncio
    async def test_returns_200(self):
        app = _make_app()

        with patch("app.api.v1.endpoints.events.event_service") as mock_svc, \
             patch("app.api.v1.endpoints.events.check_rate_limit", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.events.get_db_connection") as mock_db:
            mock_svc.list_events = AsyncMock(return_value=_event_list_response())
            mock_conn = AsyncMock()
            mock_db.return_value = mock_conn

            async def fake_db_dep():
                return mock_conn

            app.dependency_overrides[__import__("app.db.session", fromlist=["get_db_connection"]).get_db_connection] = fake_db_dep

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/events")
            assert resp.status_code == 200


class TestGetEvent:
    @pytest.mark.asyncio
    async def test_not_found_returns_404(self):
        app = _make_app()

        with patch("app.api.v1.endpoints.events.event_service") as mock_svc, \
             patch("app.api.v1.endpoints.events.check_rate_limit", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.events.get_db_connection") as mock_db:
            mock_svc.get_event = AsyncMock(side_effect=ValueError("Event not found"))
            mock_conn = AsyncMock()

            async def fake_db_dep():
                return mock_conn

            from app.db.session import get_db_connection
            app.dependency_overrides[get_db_connection] = fake_db_dep

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/events/evt_nonexistent")
            assert resp.status_code == 404


class TestGetLeaderboard:
    @pytest.mark.asyncio
    async def test_returns_200(self):
        app = _make_app()

        with patch("app.api.v1.endpoints.events.event_service") as mock_svc, \
             patch("app.api.v1.endpoints.events.check_rate_limit", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.events.get_db_connection") as mock_db:
            mock_svc.get_leaderboard = AsyncMock(return_value=_leaderboard_response())
            mock_conn = AsyncMock()

            async def fake_db_dep():
                return mock_conn

            from app.db.session import get_db_connection
            app.dependency_overrides[get_db_connection] = fake_db_dep

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/events/evt_test12345678/leaderboard")
            assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────
# Auth-required endpoints
# ─────────────────────────────────────────────────────────────────────

class TestJoinEvent:
    @pytest.mark.asyncio
    async def test_join_requires_auth(self):
        """Without auth, join should return 401."""
        app = _make_app()

        with patch("app.api.v1.endpoints.events.check_rate_limit", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.events.check_user_rate_limit", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.events.get_db_connection") as mock_db:
            mock_conn = AsyncMock()

            async def fake_db_dep():
                return mock_conn

            from app.db.session import get_db_connection
            app.dependency_overrides[get_db_connection] = fake_db_dep

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/events/evt_1/join")
            # 401 or 403 since no auth
            assert resp.status_code in (401, 403, 422)


class TestSubmitScore:
    @pytest.mark.asyncio
    async def test_submit_requires_auth(self):
        app = _make_app()

        with patch("app.api.v1.endpoints.events.check_rate_limit", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.events.check_user_rate_limit", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.events.get_db_connection") as mock_db:
            mock_conn = AsyncMock()

            async def fake_db_dep():
                return mock_conn

            from app.db.session import get_db_connection
            app.dependency_overrides[get_db_connection] = fake_db_dep

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/events/evt_1/score",
                    json={"score_delta": 10},
                )
            assert resp.status_code in (401, 403, 422)


# ─────────────────────────────────────────────────────────────────────
# Admin endpoints
# ─────────────────────────────────────────────────────────────────────

class TestAdminCreateEvent:
    @pytest.mark.asyncio
    async def test_create_requires_admin(self):
        app = _make_app()
        now = _now()

        with patch("app.api.v1.endpoints.events.check_rate_limit", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.events.get_db_connection") as mock_db:
            mock_conn = AsyncMock()

            async def fake_db_dep():
                return mock_conn

            from app.db.session import get_db_connection
            app.dependency_overrides[get_db_connection] = fake_db_dep

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/admin/events",
                    json={
                        "title": "Test Event Long Enough",
                        "description": "This is enough text for the validator check",
                        "xp_multiplier": 1.5,
                        "start_at": now.isoformat(),
                        "end_at": (now + timedelta(hours=24)).isoformat(),
                    },
                )
            # 401 or 403 since no admin auth
            assert resp.status_code in (401, 403, 422)
