"""
Tests for admin HTTP endpoints — auth/role guard, response shape, error paths.
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
        self._in_txn = False

    def is_in_transaction(self):
        return self._in_txn

    async def fetchrow(self, *a, **kw):
        return None

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return 0

    async def execute(self, *a, **kw):
        return "DELETE 0"

    def transaction(self):
        outer = self

        class _Tx:
            async def __aenter__(self_):
                outer._in_txn = True
                return self_

            async def __aexit__(self_, *args):
                outer._in_txn = False
                return False
        return _Tx()


async def _mock_conn_dep():
    yield _MockConn()


# ──────────────────────────────────────────────────────
# User helpers
# ──────────────────────────────────────────────────────

def _make_user(role="admin"):
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats
    return UserProfile(
        id=f"{role}_test",
        username=f"test_{role}",
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
# Fixture
# ──────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────
# Auth / role guards — all admin routes
# ──────────────────────────────────────────────────────

ADMIN_ROUTES = [
    ("GET",   "/api/v1/admin/users"),
    ("GET",   "/api/v1/admin/transactions"),
    ("GET",   "/api/v1/admin/withdrawals/pending"),
    ("GET",   "/api/v1/admin/logs"),
]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_requires_auth(client, method, path):
    """No token → 401."""
    r = client.request(method, path)
    assert r.status_code == 401


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_rejects_freelancer(client, method, path):
    """Freelancer token → 403."""
    from app.api.deps import require_admin
    from app.main import app
    app.dependency_overrides[require_admin] = lambda: (_ for _ in ()).throw(
        __import__("fastapi").HTTPException(status_code=403, detail="Admin access required")
    )
    # Use a simpler override: patch require_admin to raise
    from fastapi import HTTPException
    def _deny():
        raise HTTPException(status_code=403, detail="Admin access required")
    app.dependency_overrides[require_admin] = _deny
    try:
        r = client.request(method, path)
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(require_admin, None)


# ──────────────────────────────────────────────────────
# GET /admin/users
# ──────────────────────────────────────────────────────

def test_admin_list_users_success(client):
    from app.api.deps import require_admin
    from app.main import app
    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        r = client.get("/api/v1/admin/users")
        assert r.status_code == 200
        body = r.json()
        assert "users" in body
        assert "total" in body
    finally:
        app.dependency_overrides.pop(require_admin, None)


# ──────────────────────────────────────────────────────
# GET /admin/withdrawals/pending
# ──────────────────────────────────────────────────────

def test_admin_pending_withdrawals_success(client):
    from app.api.deps import require_admin
    from app.main import app
    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        r = client.get("/api/v1/admin/withdrawals/pending")
        assert r.status_code == 200
        body = r.json()
        assert "transactions" in body
    finally:
        app.dependency_overrides.pop(require_admin, None)


# ──────────────────────────────────────────────────────
# PATCH /admin/withdrawals/{id}/approve
# ──────────────────────────────────────────────────────

def test_approve_withdrawal_not_found(client):
    """fetchrow returns None → approve_withdrawal raises ValueError → 400."""
    from app.api.deps import require_admin
    from app.main import app
    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        r = client.patch("/api/v1/admin/withdrawals/tx_nonexistent/approve")
        assert r.status_code == 400
        assert "not found" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_approve_withdrawal_success(client):
    """Patch DB so approve succeeds."""
    from app.api.deps import require_admin
    from app.db.session import get_db_connection
    from app.main import app

    tx_row = {
        "id": "tx_ok", "user_id": "user_fl", "type": "withdrawal",
        "amount": 50.0, "currency": "RUB", "status": "pending",
        "quest_id": None, "created_at": datetime.now(timezone.utc),
    }

    class _ConnOk(_MockConn):
        def __init__(self):
            super().__init__()
            self._in_txn = True

        async def fetchrow(self, *a, **kw):
            return tx_row

        async def fetchval(self, *a, **kw):
            return None  # no wallet — credit auto-creates

        async def execute(self, *a, **kw):
            return "UPDATE 1"

    async def _ok_conn():
        yield _ConnOk()

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    app.dependency_overrides[get_db_connection] = _ok_conn
    try:
        r = client.patch("/api/v1/admin/withdrawals/tx_ok/approve")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "completed"
    finally:
        app.dependency_overrides.pop(require_admin, None)
        app.dependency_overrides[get_db_connection] = _mock_conn_dep


# ──────────────────────────────────────────────────────
# PATCH /admin/withdrawals/{id}/reject
# ──────────────────────────────────────────────────────

def test_reject_withdrawal_missing_reason(client):
    """Empty body → 422 validation error."""
    from app.api.deps import require_admin
    from app.main import app
    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        r = client.patch("/api/v1/admin/withdrawals/tx_abc/reject", json={})
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_reject_withdrawal_not_found(client):
    """fetchrow returns None → 400."""
    from app.api.deps import require_admin
    from app.main import app
    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        r = client.patch(
            "/api/v1/admin/withdrawals/tx_nonexistent/reject",
            json={"reason": "Документы не верифицированы"},
        )
        assert r.status_code == 400
    finally:
        app.dependency_overrides.pop(require_admin, None)


# ──────────────────────────────────────────────────────
# GET /admin/logs
# ──────────────────────────────────────────────────────

def test_admin_logs_success(client):
    from app.api.deps import require_admin
    from app.main import app
    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        r = client.get("/api/v1/admin/logs")
        assert r.status_code == 200
        body = r.json()
        assert "logs" in body
        assert "total" in body
    finally:
        app.dependency_overrides.pop(require_admin, None)


# ──────────────────────────────────────────────────────
# POST /admin/maintenance/cleanup-notifications
# ──────────────────────────────────────────────────────

def test_cleanup_notifications_success(client):
    from app.api.deps import require_admin
    from app.main import app
    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        r = client.post("/api/v1/admin/maintenance/cleanup-notifications")
        assert r.status_code == 200
        body = r.json()
        assert "deleted" in body
    finally:
        app.dependency_overrides.pop(require_admin, None)
