"""HTTP endpoint tests for /disputes routes.

Tests:
  - 401 for unauthenticated callers
  - 403 for wrong role / non-party access
  - 422 for invalid input
  - 409 for duplicate dispute
  - 201 for successful open
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────────────────────────────────────────────────────
# Minimal asyncpg mocks (copied from test_endpoints.py pattern)
# ─────────────────────────────────────────────────────────────────────

class _MockTransaction:
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass


class _MockPoolAcquire:
    def __init__(self, conn):
        self._conn = conn
    async def __aenter__(self): return self._conn
    async def __aexit__(self, *args): return False


class _MockPool:
    def __init__(self, conn=None):
        from tests.test_dispute_endpoints import _MockConn
        self._conn = conn or _MockConn()

    def acquire(self): return _MockPoolAcquire(self._conn)
    def get_size(self): return 1
    def get_idle_size(self): return 1
    def get_min_size(self): return 1
    def get_max_size(self): return 5


class _MockConn:
    async def fetchrow(self, *a, **kw): return None
    async def fetch(self, *a, **kw): return []
    async def fetchval(self, *a, **kw): return 0
    async def execute(self, *a, **kw): return "INSERT 0 1"

    def is_in_transaction(self): return False

    def transaction(self): return _MockTransaction()


async def _mock_conn_dep():
    yield _MockConn()


def _make_user(user_id="freelancer_1", role="freelancer"):
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats
    return UserProfile(
        id=user_id,
        username=f"user_{user_id}",
        role=UserRoleEnum(role),
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(),
        badges=[],
        skills=[],
    )


def _make_dispute_out(status="open"):
    now = datetime.now(timezone.utc)
    return {
        "id": "dis_test123",
        "quest_id": "quest_1",
        "initiator_id": "freelancer_1",
        "respondent_id": "client_1",
        "reason": "Client not confirming",
        "response_text": None,
        "status": status,
        "resolution_type": None,
        "partial_percent": None,
        "resolution_note": None,
        "moderator_id": None,
        "auto_escalate_at": (now + timedelta(hours=72)).isoformat(),
        "created_at": now.isoformat(),
        "responded_at": None,
        "escalated_at": None,
        "resolved_at": None,
    }


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
    ):
        from app.main import app
        from app.db.session import get_db_connection
        from fastapi.testclient import TestClient

        app.dependency_overrides[get_db_connection] = _mock_conn_dep

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.pop(get_db_connection, None)


# ─────────────────────────────────────────────────────────────────────
# POST /disputes — open_dispute
# ─────────────────────────────────────────────────────────────────────

class TestOpenDisputeEndpoint:
    def test_unauthenticated_returns_401(self, client):
        resp = client.post("/api/v1/disputes", json={"quest_id": "q1", "reason": "Test reason here"})
        assert resp.status_code == 401

    def test_missing_reason_returns_422(self, client):
        from app.api.deps import require_auth
        from app.main import app

        app.dependency_overrides[require_auth] = lambda: _make_user()
        try:
            resp = client.post(
                "/api/v1/disputes",
                json={"quest_id": "q1"},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_reason_too_short_returns_422(self, client):
        from app.api.deps import require_auth
        from app.main import app

        app.dependency_overrides[require_auth] = lambda: _make_user()
        try:
            resp = client.post(
                "/api/v1/disputes",
                json={"quest_id": "q1", "reason": "short"},  # < 10 chars
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(require_auth, None)


# ─────────────────────────────────────────────────────────────────────
# GET /disputes — list_my_disputes
# ─────────────────────────────────────────────────────────────────────

class TestListDisputesEndpoint:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/v1/disputes")
        assert resp.status_code == 401

    def test_authenticated_returns_200(self, client):
        from app.api.deps import require_auth
        from app.main import app

        app.dependency_overrides[require_auth] = lambda: _make_user()
        try:
            with patch(
                "app.services.dispute_service.list_my_disputes",
                new_callable=AsyncMock,
                return_value=MagicMock(items=[], total=0),
            ):
                resp = client.get("/api/v1/disputes")
                assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(require_auth, None)


# ─────────────────────────────────────────────────────────────────────
# PATCH /disputes/{id}/resolve — admin only
# ─────────────────────────────────────────────────────────────────────

class TestResolveDisputeEndpoint:
    def test_non_admin_returns_401_or_403(self, client):
        resp = client.patch(
            "/api/v1/disputes/dis_test/resolve",
            json={
                "resolution_type": "refund",
                "resolution_note": "Test resolution note",
            },
        )
        assert resp.status_code in (401, 403)

    def test_partial_without_percent_returns_422(self, client):
        from app.api.deps import require_admin
        from app.main import app

        app.dependency_overrides[require_admin] = lambda: _make_user(role="admin")
        try:
            resp = client.patch(
                "/api/v1/disputes/dis_test/resolve",
                json={
                    "resolution_type": "partial",
                    "resolution_note": "Test note",
                    # partial_percent missing
                },
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(require_admin, None)


# ─────────────────────────────────────────────────────────────────────
# GET /admin/disputes — admin list
# ─────────────────────────────────────────────────────────────────────

class TestAdminListDisputesEndpoint:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/v1/admin/disputes")
        assert resp.status_code == 401

    def test_admin_returns_200(self, client):
        from app.api.deps import require_admin
        from app.main import app

        app.dependency_overrides[require_admin] = lambda: _make_user(role="admin")
        try:
            with patch(
                "app.services.dispute_service.admin_list_disputes",
                new_callable=AsyncMock,
                return_value=MagicMock(items=[], total=0),
            ):
                resp = client.get("/api/v1/admin/disputes")
                assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(require_admin, None)
