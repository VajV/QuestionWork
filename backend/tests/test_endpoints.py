"""HTTP endpoint tests â€" API contract and input validation.

Tests run without a real database by mocking asyncpg connections and the DB
pool lifecycle.  Scope is intentionally narrow: we verify that:

  â€¢ Pydantic validation rejects malformed input with 422
  â€¢ Protected endpoints reject unauthenticated callers with 401
  â€¢ Role-guarded endpoints reject wrong-role callers with 403
  â€¢ Valid requests reach the handler (200/201 from mocked data)
"""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Minimal asyncpg Connection mock
# ---------------------------------------------------------------------------


class _MockConn:
    """Asyncpg Connection mock â€" all queries return empty/nothing."""

    async def fetchrow(self, *a, **kw):
        return None

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return 0

    async def execute(self, *a, **kw):
        return "INSERT 0 1"


async def _mock_conn_dep():
    """Async generator that yields a MockConn â€" replaces get_db_connection."""
    yield _MockConn()


# ---------------------------------------------------------------------------
# Module-scoped TestClient fixture (app started once for all tests here)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Helper to build a fake UserProfile for dependency-override tests
# ---------------------------------------------------------------------------


def _make_user(role: str = "client"):
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


# ---------------------------------------------------------------------------
# POST /auth/register â€" validation
# ---------------------------------------------------------------------------


def test_register_missing_fields(client):
    r = client.post("/api/v1/auth/register", json={})
    assert r.status_code == 422


def test_register_username_too_short(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "ab", "email": "ok@test.com", "password": "SecurePass1"},
    )
    assert r.status_code == 422


def test_register_password_too_short(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "validuser", "email": "ok@test.com", "password": "short"},
    )
    assert r.status_code == 422


def test_register_invalid_email(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "validuser", "email": "not-an-email", "password": "SecurePass1"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login â€" validation
# ---------------------------------------------------------------------------


def test_login_username_too_long(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "x" * 51, "password": "SomePassword1"},
    )
    assert r.status_code == 422


def test_login_password_too_long(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "validuser", "password": "x" * 129},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /users/ â€" auth guard
# ---------------------------------------------------------------------------


def test_users_list_requires_auth(client):
    """No auth header â†' 401."""
    r = client.get("/api/v1/users/")
    assert r.status_code == 401


def test_users_list_accepts_bearer(client):
    """Proper JWT via dependency override â†' 200."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        r = client.get("/api/v1/users/")
        assert r.status_code == 200
        assert r.json() == []
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_users_list_rejects_non_bearer(client):
    """Basic auth format is not accepted â†' 401."""
    r = client.get("/api/v1/users/", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /quests/ â€" auth + role + validation
# ---------------------------------------------------------------------------


def test_create_quest_unauthenticated(client):
    """No auth â†' 401."""
    r = client.post(
        "/api/v1/quests/",
        json={
            "title": "Valid title here",
            "description": "A sufficiently long description for the quest",
            "budget": 1000,
            "currency": "RUB",
        },
    )
    assert r.status_code == 401


def test_create_quest_freelancer_forbidden(client):
    """Freelancer role â†' 403."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        r = client.post(
            "/api/v1/quests/",
            json={
                "title": "Valid title here",
                "description": "A sufficiently long description for the quest",
                "budget": 1000,
                "currency": "RUB",
            },
        )
        assert r.status_code == 403
        assert "client" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_create_quest_budget_below_minimum(client):
    """Budget < 100 â†' 422."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        r = client.post(
            "/api/v1/quests/",
            json={
                "title": "Valid title here",
                "description": "A sufficiently long description for the quest",
                "budget": 50,
                "currency": "RUB",
            },
        )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_create_quest_budget_above_maximum(client):
    """Budget > 1_000_000 â†' 422."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        r = client.post(
            "/api/v1/quests/",
            json={
                "title": "Valid title here",
                "description": "A sufficiently long description for the quest",
                "budget": 2_000_000,
                "currency": "RUB",
            },
        )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_create_quest_skills_too_many(client):
    """More than 20 skills â†' 422."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        r = client.post(
            "/api/v1/quests/",
            json={
                "title": "Valid title here",
                "description": "A sufficiently long description for the quest",
                "budget": 1000,
                "currency": "RUB",
                "skills": [f"skill_{i}" for i in range(21)],
            },
        )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_create_quest_invalid_currency(client):
    """Currency not in [USD, EUR, RUB] â†' 422."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        r = client.post(
            "/api/v1/quests/",
            json={
                "title": "Valid title here",
                "description": "A sufficiently long description for the quest",
                "budget": 1000,
                "currency": "JPY",
            },
        )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# POST /quests/{id}/apply â€" application validation
# ---------------------------------------------------------------------------


def test_apply_cover_letter_too_short(client):
    """Cover letter with < 10 chars â†' 422."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        r = client.post(
            "/api/v1/quests/some_quest_id/apply",
            json={"cover_letter": "Too short", "proposed_price": 1000},
        )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_apply_negative_price_rejected(client):
    """Negative proposed_price â†' 422."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        r = client.post(
            "/api/v1/quests/some_quest_id/apply",
            json={
                "cover_letter": "I am very interested in this project and have all required skills.",
                "proposed_price": -100,
            },
        )
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# GET /quests/ — public list
# ---------------------------------------------------------------------------


def test_get_quest_list_ok(client):
    """GET /quests/ is public and returns paginated response even when DB is empty."""
    r = client.get("/api/v1/quests/")
    assert r.status_code == 200
    body = r.json()
    assert "quests" in body
    assert body["quests"] == []
    assert body["total"] == 0
    assert "page" in body


def test_get_quest_list_with_filters(client):
    """GET /quests/ accepts filter params without erroring."""
    r = client.get("/api/v1/quests/?status_filter=open&page=1&page_size=5")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /quests/{id} — quest detail
# ---------------------------------------------------------------------------


def test_get_quest_not_found(client):
    """GET /quests/{id} — mock DB returns None → 404."""
    r = client.get("/api/v1/quests/nonexistent-quest-id")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /quests/{id}/apply — auth guard
# ---------------------------------------------------------------------------


def test_apply_to_quest_unauthenticated(client):
    """POST /quests/{id}/apply without auth header → 401."""
    r = client.post(
        "/api/v1/quests/some_id/apply",
        json={
            "cover_letter": "Very interested in this quest, ready to start immediately.",
            "proposed_price": 1000,
        },
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /quests/{id}/assign — auth guard
# ---------------------------------------------------------------------------


def test_assign_quest_unauthenticated(client):
    """POST /quests/{id}/assign without auth → 401."""
    r = client.post("/api/v1/quests/some_id/assign?freelancer_id=user_123")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /quests/{id}/complete — auth guard
# ---------------------------------------------------------------------------


def test_complete_quest_unauthenticated(client):
    """POST /quests/{id}/complete without auth → 401."""
    r = client.post("/api/v1/quests/some_id/complete")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /quests/{id}/confirm — auth guard
# ---------------------------------------------------------------------------


def test_confirm_quest_unauthenticated(client):
    """POST /quests/{id}/confirm without auth → 401."""
    r = client.post("/api/v1/quests/some_id/confirm")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /quests/{id}/cancel — auth guard
# ---------------------------------------------------------------------------


def test_cancel_quest_unauthenticated(client):
    """POST /quests/{id}/cancel without auth → 401."""
    r = client.post("/api/v1/quests/some_id/cancel")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /quests/{id}/applications — auth guard
# ---------------------------------------------------------------------------


def test_get_applications_unauthenticated(client):
    """GET /quests/{id}/applications without auth → 401."""
    r = client.get("/api/v1/quests/some_id/applications")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /users/{id} — user profile
# ---------------------------------------------------------------------------


def test_get_user_profile_not_found(client):
    """GET /users/{id} — mock DB returns None → 404."""
    r = client.get("/api/v1/users/nonexistent-user-id")
    assert r.status_code == 404


def test_get_user_profile_public(client):
    """GET /users/{id} is public (no auth required) — 404 not 401 when user missing."""
    r = client.get("/api/v1/users/missing-id-xyz")
    # Public endpoint: returns 404, NOT 401
    assert r.status_code != 401
    assert r.status_code == 404
