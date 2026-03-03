"""Tests for notification HTTP endpoints — auth guard, list shape, mark-read."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


# ──────────────────────────────────────────────────
# Minimal asyncpg Connection mock
# ──────────────────────────────────────────────────

class _MockConn:
    def is_in_transaction(self):
        return False

    async def fetchrow(self, *a, **kw):
        return None

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return 0

    async def execute(self, *a, **kw):
        return "UPDATE 0"

    def transaction(self):
        class _Tx:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
        return _Tx()


async def _mock_conn_dep():
    yield _MockConn()


# ──────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────

def _make_user(role="freelancer"):
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats

    return UserProfile(
        id="user_test",
        username="test_user",
        role=UserRoleEnum(role),
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(),
        badges=[],
        skills=[],
    )


# ──────────────────────────────────────────────────
# Fixture
# ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
    ):
        from app.main import app
        from app.db.session import get_db_connection

        app.dependency_overrides[get_db_connection] = _mock_conn_dep

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.pop(get_db_connection, None)


# ──────────────────────────────────────────────────
# GET /notifications
# ──────────────────────────────────────────────────

def test_list_notifications_requires_auth(client):
    r = client.get("/api/v1/notifications")
    assert r.status_code == 401


def test_list_notifications_authenticated(client):
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user()
    try:
        r = client.get("/api/v1/notifications")
        assert r.status_code == 200
        body = r.json()
        assert "notifications" in body
        assert "total" in body
        assert "unread_count" in body
        assert isinstance(body["notifications"], list)
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_list_notifications_unread_only_flag(client):
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user()
    try:
        r = client.get("/api/v1/notifications?unread_only=true")
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ──────────────────────────────────────────────────
# PATCH /notifications/{id}/read
# ──────────────────────────────────────────────────

def test_mark_notification_read_requires_auth(client):
    r = client.patch("/api/v1/notifications/notif_abc/read")
    assert r.status_code == 401


def test_mark_notification_read_not_found(client):
    """execute returns 'UPDATE 0' → 404."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user()
    try:
        r = client.patch("/api/v1/notifications/notif_nonexistent/read")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_mark_notification_read_success(client):
    """Patch conn so execute returns 'UPDATE 1' → 200."""
    from app.api.deps import require_auth
    from app.db.session import get_db_connection
    from app.main import app

    class _ConnUpdate1(_MockConn):
        async def execute(self, *a, **kw):
            return "UPDATE 1"

    async def _conn_update1():
        yield _ConnUpdate1()

    app.dependency_overrides[require_auth] = lambda: _make_user()
    app.dependency_overrides[get_db_connection] = _conn_update1
    try:
        r = client.patch("/api/v1/notifications/notif_abc/read")
        assert r.status_code == 200
        body = r.json()
        assert body.get("is_read") is True
    finally:
        app.dependency_overrides.pop(require_auth, None)
        app.dependency_overrides[get_db_connection] = _mock_conn_dep


# ──────────────────────────────────────────────────
# POST /notifications/read-all
# ──────────────────────────────────────────────────

def test_read_all_requires_auth(client):
    r = client.post("/api/v1/notifications/read-all")
    assert r.status_code == 401


def test_read_all_authenticated(client):
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user()
    try:
        r = client.post("/api/v1/notifications/read-all")
        assert r.status_code == 200
        body = r.json()
        assert "marked_read" in body
    finally:
        app.dependency_overrides.pop(require_auth, None)
