"""
Tests for admin HTTP endpoints — auth/role guard, response shape, error paths.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from types import SimpleNamespace

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


def test_admin_force_complete_returns_409_when_escrow_state_is_inconsistent(client):
    from app.api.deps import require_admin
    from app.main import app
    from app.services.wallet_service import EscrowMismatchError

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        with patch(
            "app.api.v1.endpoints.admin.admin_service.force_complete_quest",
            new=AsyncMock(side_effect=EscrowMismatchError("Escrow hold amount does not match payout amount")),
        ):
            response = client.post(
                "/api/v1/admin/quests/quest_123/force-complete",
                json={"reason": "Admin remediation path"},
            )

        assert response.status_code == 409
        assert response.json()["detail"] == "Quest payment state is inconsistent. Please contact support."
    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.parametrize(
    ("payload", "expected_fragment"),
    [
        ({"skills": ["python", 123]}, "string_type"),
        ({"skills": [f"skill_{idx}" for idx in range(21)]}, "at most 20 items"),
        ({"skills": ["x" * 51]}, "at most 50 characters"),
    ],
)
def test_admin_update_user_rejects_invalid_skills_payload(client, payload, expected_fragment):
    from app.api.deps import require_admin
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        response = client.patch("/api/v1/admin/users/user_123", json=payload)

        assert response.status_code == 422
        assert expected_fragment in response.text
    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_admin_rate_limit_scoped_by_route(monkeypatch):
    from app.api.v1.endpoints import admin as admin_endpoints

    captured_actions: list[str] = []

    async def _fake_check_rate_limit(ip: str, action: str, limit: int, window_seconds: int):
        captured_actions.append(action)

    monkeypatch.setattr(admin_endpoints, "check_rate_limit", _fake_check_rate_limit)

    users_request = MagicMock()
    users_request.method = "GET"
    users_request.url.path = "/api/v1/admin/users"
    users_request.scope = {"route": SimpleNamespace(path="/api/v1/admin/users")}
    users_request.client = SimpleNamespace(host="127.0.0.1")
    users_request.headers = {}

    logs_request = MagicMock()
    logs_request.method = "GET"
    logs_request.url.path = "/api/v1/admin/logs"
    logs_request.scope = {"route": SimpleNamespace(path="/api/v1/admin/logs")}
    logs_request.client = SimpleNamespace(host="127.0.0.1")
    logs_request.headers = {}

    await admin_endpoints._admin_rate_limit(users_request)
    await admin_endpoints._admin_rate_limit(logs_request)

    assert captured_actions == [
        "admin:GET:/api/v1/admin/users",
        "admin:GET:/api/v1/admin/logs",
    ]


@pytest.mark.asyncio
async def test_admin_rate_limit_falls_back_to_request_path(monkeypatch):
    from app.api.v1.endpoints import admin as admin_endpoints

    captured_actions: list[str] = []

    async def _fake_check_rate_limit(ip: str, action: str, limit: int, window_seconds: int):
        captured_actions.append(action)

    monkeypatch.setattr(admin_endpoints, "check_rate_limit", _fake_check_rate_limit)

    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/admin/notifications/broadcast"
    request.scope = {}
    request.client = SimpleNamespace(host="127.0.0.1")
    request.headers = {}

    await admin_endpoints._admin_rate_limit(request)

    assert captured_actions == ["admin:POST:/api/v1/admin/notifications/broadcast"]


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


def test_admin_upsert_guild_season_reward_config_success(client, monkeypatch):
    from app.api.deps import require_admin
    from app.api.v1.endpoints import admin as admin_endpoints
    from app.main import app

    async def _fake_upsert(conn, payload, admin_id, ip_address):
        return {
            "id": "gsrc_banner_forge",
            "season_code": payload["season_code"],
            "family": payload["family"],
            "label": payload["label"],
            "accent": payload["accent"],
            "treasury_bonus": payload["treasury_bonus"],
            "guild_tokens_bonus": payload["guild_tokens_bonus"],
            "badge_name": payload["badge_name"],
            "is_active": payload["is_active"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(admin_endpoints.admin_service, "upsert_guild_season_reward_config", _fake_upsert)
    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        response = client.post(
            "/api/v1/admin/guild-season-rewards",
            json={
                "season_code": "forge-awakening",
                "family": "banner",
                "label": "Storm campaign reserve",
                "accent": "cyan",
                "treasury_bonus": "40.00",
                "guild_tokens_bonus": 3,
                "badge_name": "Storm Standard",
                "is_active": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["family"] == "banner"
        assert body["badge_name"] == "Storm Standard"
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_broadcast_notification_empty_user_ids_returns_422(client):
    """P2-2: Submitting user_ids=[] must return HTTP 422."""
    from app.api.deps import require_admin
    from app.main import app
    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        r = client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"user_ids": [], "title": "Test", "message": "Test message"},
        )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_admin, None)
