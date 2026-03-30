"""
Tests for analytics service and HTTP endpoint.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from fastapi.testclient import TestClient


# ──────────────────────────────────────────────────────
# Mock DB connection
# ──────────────────────────────────────────────────────

class _MockConn:
    def __init__(self):
        self._executed: list[tuple] = []
        self._fetch_result = [{}]

    def is_in_transaction(self):
        return False

    async def execute(self, query, *args, **kwargs):
        self._executed.append((query, args))
        return "INSERT 0 1"

    async def fetch(self, query, *args, **kwargs):
        return self._fetch_result

    async def fetchrow(self, *a, **kw):
        return None

    async def fetchval(self, *a, **kw):
        return None

    def transaction(self):
        class _Tx:
            async def __aenter__(self_):
                return self_
            async def __aexit__(self_, *args):
                return False
        return _Tx()


async def _mock_conn_dep():
    yield _MockConn()


# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────

def _make_user(role="client"):
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats
    return UserProfile(
        id=f"{role}_analytics_test",
        username=f"analytics_{role}",
        role=UserRoleEnum(role),
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(),
        badges=[],
        skills=[],
    )


# ──────────────────────────────────────────────────────
# analytics_service unit tests
# ──────────────────────────────────────────────────────

class TestAnalyticsServiceIngestEvent:
    @pytest.mark.asyncio
    async def test_ingest_single_event_executes_insert(self):
        from app.services.analytics_service import ingest_event

        conn = _MockConn()
        await ingest_event(
            conn,
            event_name="landing_view",
            user_id="user_abc",
            session_id="sess_xyz",
            role="client",
            source="organic",
            path="/",
            properties={"referrer": "google"},
        )

        assert len(conn._executed) == 1
        query, args = conn._executed[0]
        assert "INSERT INTO analytics_events" in query
        assert args[0] == "landing_view"
        assert args[1] == "user_abc"

    @pytest.mark.asyncio
    async def test_ingest_event_without_user(self):
        from app.services.analytics_service import ingest_event

        conn = _MockConn()
        await ingest_event(
            conn,
            event_name="landing_view",
            user_id=None,
            session_id=None,
            role=None,
            source=None,
            path="/",
            properties={},
        )

        assert len(conn._executed) == 1


class TestAnalyticsServiceBatch:
    @pytest.mark.asyncio
    async def test_batch_inserts_all_events(self):
        from app.services.analytics_service import ingest_events_batch

        conn = _MockConn()
        events = [
            {"event_name": "landing_view", "path": "/"},
            {"event_name": "register_started", "path": "/auth/register"},
        ]
        count = await ingest_events_batch(conn, user_id="user_123", events=events)

        assert count == 2
        assert len(conn._executed) == 2

    @pytest.mark.asyncio
    async def test_batch_skips_invalid_events(self):
        from app.services.analytics_service import ingest_events_batch

        conn = _MockConn()
        # Inject a failure on second execute
        call_count = [0]
        original_execute = conn.execute

        async def failing_execute(query, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("DB error")
            return await original_execute(query, *args, **kwargs)

        conn.execute = failing_execute

        events = [
            {"event_name": "landing_view", "path": "/"},
            {"event_name": "bad_event", "path": "/"},
            {"event_name": "register_started", "path": "/auth/register"},
        ]
        count = await ingest_events_batch(conn, user_id=None, events=events)

        # 2 should succeed, 1 should be skipped (the failing one)
        assert count == 2

    @pytest.mark.asyncio
    async def test_empty_batch_returns_zero(self):
        from app.services.analytics_service import ingest_events_batch

        conn = _MockConn()
        count = await ingest_events_batch(conn, user_id=None, events=[])
        assert count == 0


class TestAnalyticsRetention:
    @pytest.mark.asyncio
    async def test_prune_old_events_deletes_rows_older_than_retention_window(self):
        from app.services.analytics_service import prune_old_events

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=17)

        deleted = await prune_old_events(conn, retention_days=90)

        assert deleted == 17
        query = conn.fetchval.await_args.args[0]
        assert "DELETE FROM analytics_events" in query
        assert conn.fetchval.await_args.args[1] == 90


# ──────────────────────────────────────────────────────
# HTTP endpoint tests
# ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from app.db.session import get_db_connection
    from app.api.deps import get_current_user
    from app.main import app

    with (
        patch.object(app, "dependency_overrides", {}) as _,
    ):
        app.dependency_overrides[get_db_connection] = _mock_conn_dep
        app.dependency_overrides[get_current_user] = lambda: None
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


class TestAnalyticsEndpoint:
    def test_ingest_single_event_returns_ok(self, client):
        response = client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_name": "landing_view",
                        "path": "/",
                        "properties": {},
                    }
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 1

    def test_ingest_batch_multiple_events(self, client):
        response = client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {"event_name": "landing_view", "path": "/"},
                    {"event_name": "register_started", "path": "/auth/register"},
                    {"event_name": "marketplace_view", "path": "/marketplace"},
                ]
            },
        )
        assert response.status_code == 200
        assert response.json()["ingested"] == 3

    def test_empty_events_list_returns_422(self, client):
        response = client.post(
            "/api/v1/analytics/events",
            json={"events": []},
        )
        assert response.status_code == 422

    def test_too_many_events_returns_422(self, client):
        events = [{"event_name": "landing_view", "path": "/"} for _ in range(51)]
        response = client.post(
            "/api/v1/analytics/events",
            json={"events": events},
        )
        assert response.status_code == 422

    def test_missing_event_name_returns_422(self, client):
        response = client.post(
            "/api/v1/analytics/events",
            json={"events": [{"path": "/"}]},
        )
        assert response.status_code == 422

    def test_event_with_all_optional_fields(self, client):
        response = client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_name": "profile_view",
                        "path": "/users/user_abc",
                        "session_id": "sess_001",
                        "role": "client",
                        "source": "marketplace",
                        "properties": {"viewed_user_id": "user_abc"},
                        "timestamp": "2026-03-12T10:00:00Z",
                    }
                ]
            },
        )
        assert response.status_code == 200
        assert response.json()["ingested"] == 1
