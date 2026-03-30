"""HTTP endpoint tests â€" API contract and input validation.

Tests run without a real database by mocking asyncpg connections and the DB
pool lifecycle.  Scope is intentionally narrow: we verify that:

  â€¢ Pydantic validation rejects malformed input with 422
  â€¢ Protected endpoints reject unauthenticated callers with 401
  â€¢ Role-guarded endpoints reject wrong-role callers with 403
  â€¢ Valid requests reach the handler (200/201 from mocked data)
"""

import pytest
import importlib
import sys
import types
import asyncpg
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Minimal asyncpg Connection mock
# ---------------------------------------------------------------------------


class _MockTransaction:
    """Fake asyncpg transaction context manager."""
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass


class _MockPoolAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        return False


class _MockPool:
    def __init__(self, conn=None):
        self._conn = conn or _MockConn()

    def acquire(self):
        return _MockPoolAcquire(self._conn)

    def get_size(self):
        return 1

    def get_idle_size(self):
        return 1

    def get_min_size(self):
        return 1

    def get_max_size(self):
        return 5


class _MockConn:
    """Asyncpg Connection mock — all queries return empty/nothing."""

    async def fetchrow(self, *a, **kw):
        return None

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return 0

    async def execute(self, *a, **kw):
        return "INSERT 0 1"

    def transaction(self):
        return _MockTransaction()


async def _mock_conn_dep():
    """Async generator that yields a MockConn â€" replaces get_db_connection."""
    yield _MockConn()


def _install_optional_dependency_stubs() -> None:
    sys.modules.setdefault("edge_tts", types.SimpleNamespace())

    if "reportlab" in sys.modules:
        return

    reportlab = types.ModuleType("reportlab")
    reportlab_lib = types.ModuleType("reportlab.lib")
    reportlab_colors = types.ModuleType("reportlab.lib.colors")
    reportlab_colors.white = object()
    reportlab_colors.black = object()
    reportlab_colors.HexColor = lambda value: value

    reportlab_pagesizes = types.ModuleType("reportlab.lib.pagesizes")
    reportlab_pagesizes.A4 = (595, 842)

    reportlab_styles = types.ModuleType("reportlab.lib.styles")
    reportlab_styles.ParagraphStyle = type("ParagraphStyle", (), {})
    reportlab_styles.getSampleStyleSheet = lambda: {
        "Heading1": object(),
        "Heading3": object(),
        "BodyText": object(),
    }

    reportlab_units = types.ModuleType("reportlab.lib.units")
    reportlab_units.mm = 1

    reportlab_pdfgen = types.ModuleType("reportlab.pdfgen")
    reportlab_canvas = types.ModuleType("reportlab.pdfgen.canvas")
    reportlab_canvas.Canvas = type("Canvas", (), {})

    reportlab_platypus = types.ModuleType("reportlab.platypus")
    reportlab_platypus.Paragraph = type("Paragraph", (), {})
    reportlab_platypus.SimpleDocTemplate = type("SimpleDocTemplate", (), {})
    reportlab_platypus.Spacer = type("Spacer", (), {})
    reportlab_platypus.Table = type("Table", (), {})
    reportlab_platypus.TableStyle = type("TableStyle", (), {})

    reportlab.lib = reportlab_lib
    reportlab.pdfgen = reportlab_pdfgen
    reportlab_lib.colors = reportlab_colors
    reportlab_lib.pagesizes = reportlab_pagesizes
    reportlab_lib.styles = reportlab_styles
    reportlab_lib.units = reportlab_units
    reportlab_pdfgen.canvas = reportlab_canvas

    sys.modules.setdefault("reportlab", reportlab)
    sys.modules.setdefault("reportlab.lib", reportlab_lib)
    sys.modules.setdefault("reportlab.lib.colors", reportlab_colors)
    sys.modules.setdefault("reportlab.lib.pagesizes", reportlab_pagesizes)
    sys.modules.setdefault("reportlab.lib.styles", reportlab_styles)
    sys.modules.setdefault("reportlab.lib.units", reportlab_units)
    sys.modules.setdefault("reportlab.pdfgen", reportlab_pdfgen)
    sys.modules.setdefault("reportlab.pdfgen.canvas", reportlab_canvas)
    sys.modules.setdefault("reportlab.platypus", reportlab_platypus)


# ---------------------------------------------------------------------------
# Module-scoped TestClient fixture (app started once for all tests here)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    _install_optional_dependency_stubs()
    main_module = importlib.import_module("app.main")
    with (
        patch.object(main_module, "init_db_pool", new_callable=AsyncMock),
        patch.object(main_module, "close_db_pool", new_callable=AsyncMock),
    ):
        app = main_module.app
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


def _make_quest_payload(status: str = "open"):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": "quest_test_1",
        "client_id": "client_test",
        "client_username": "test_client",
        "title": "Valid title here",
        "description": "A sufficiently long description for the quest payload.",
        "required_grade": "novice",
        "skills": ["python"],
        "budget": "1000.00",
        "currency": "RUB",
        "xp_reward": 100,
        "status": status,
        "applications": [],
        "assigned_to": None,
        "is_urgent": False,
        "deadline": None,
        "required_portfolio": False,
        "delivery_note": None,
        "delivery_url": None,
        "delivery_submitted_at": None,
        "revision_reason": None,
        "revision_requested_at": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }


def _chunk_bytes(payload: bytes, *, chunk_size: int = 65536):
    for start in range(0, len(payload), chunk_size):
        yield payload[start:start + chunk_size]


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


def test_register_cannot_create_admin(client):
    """P0-1: Sending role=admin must NOT create an admin user."""
    r = client.post(
        "/api/v1/auth/register",
        json={
            "username": "hacker_admin",
            "email": "hacker@test.com",
            "password": "SecurePass1!",
            "role": "admin",
        },
    )
    # Registration should succeed but user must be downgraded to freelancer
    assert r.status_code == 201
    data = r.json()
    assert data["user"]["role"] == "freelancer"


# ---------------------------------------------------------------------------
# POST /auth/login — validation
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


def test_register_accepts_chunked_body_without_content_length(client):
    payload = (
        b'{"username":"chunkeduser","email":"chunked@test.com",'
        b'"password":"SecurePass1!"}'
    )

    r = client.post(
        "/api/v1/auth/register",
        content=_chunk_bytes(payload, chunk_size=7),
        headers={"Content-Type": "application/json"},
    )

    assert r.status_code == 201


def test_login_rejects_oversized_chunked_body_without_content_length(client):
    payload = b"a" * (1024 * 1024 + 1)

    r = client.post(
        "/api/v1/auth/login",
        content=_chunk_bytes(payload),
        headers={"Content-Type": "application/json"},
    )

    assert r.status_code == 413
    assert r.json()["detail"] == "Request body too large (max 1 MB)"


# ---------------------------------------------------------------------------
# POST /auth/refresh — banned user check (P1-1)
# ---------------------------------------------------------------------------


def test_refresh_banned_user_returns_403(client):
    """P1-1: Banned user attempting /refresh must get 403."""
    from unittest.mock import patch as _patch, MagicMock
    from datetime import datetime, timezone
    from app.main import app
    from app.db.session import get_db_connection

    banned_user_row = {
        "id": "user_banned1",
        "username": "banned_guy",
        "email": "banned@test.com",
        "role": "freelancer",
        "is_banned": True,
        "banned_reason": "TOS violation",
        "level": 1,
        "grade": "novice",
        "xp": 0,
        "xp_to_next": 100,
        "stat_points": 0,
        "stats_int": 10,
        "stats_dex": 10,
        "stats_cha": 10,
        "badges": "[]",
        "bio": None,
        "skills": "[]",
        "character_class": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    class _BannedConn(_MockConn):
        async def fetchrow(self, *a, **kw):
            return banned_user_row

    async def _banned_conn():
        yield _BannedConn()

    app.dependency_overrides[get_db_connection] = _banned_conn
    try:
        # Patch rotate_refresh_token to return a user_id for our banned user
        with _patch("app.api.v1.endpoints.auth.rotate_refresh_token", return_value=("user_banned1", "new_token", 604800)), \
             _patch("app.api.v1.endpoints.auth.revoke_refresh_token"):
            client.cookies.set("refresh_token", "valid_refresh_token")
            r = client.post(
                "/api/v1/auth/refresh",
            )
        assert r.status_code == 403
        assert "banned" in r.json()["detail"].lower()
    finally:
        client.cookies.clear()
        app.dependency_overrides[get_db_connection] = _mock_conn_dep


# ---------------------------------------------------------------------------
# JWT access token TTL (P1-2)
# ---------------------------------------------------------------------------


def test_access_token_ttl_5min():
    """P1-2: Access token TTL must be <= 5 minutes."""
    from app.core.config import settings
    assert settings.JWT_EXPIRE_MINUTES <= 5


# ---------------------------------------------------------------------------
# GET /users/ — public access
# ---------------------------------------------------------------------------


def test_users_list_is_public(client):
    """No auth header -> 200 because the users list is public."""
    r = client.get("/api/v1/users/")
    assert r.status_code == 200
    body = r.json()
    assert body["users"] == []
    assert "total" in body


def test_users_list_accepts_bearer(client):
    """Authenticated callers still receive the same public-safe response."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        r = client.get("/api/v1/users/")
        assert r.status_code == 200
        body = r.json()
        assert body["users"] == []
        assert "total" in body
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_users_list_ignores_non_bearer_auth_header(client):
    """A non-Bearer auth header must not turn the public endpoint into 401."""
    r = client.get("/api/v1/users/", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert r.status_code == 200
    body = r.json()
    assert body["users"] == []
    assert "total" in body


def test_artifact_equip_requires_auth(client):
    r = client.post("/api/v1/users/me/artifacts/artifact_1/equip")
    assert r.status_code == 401


def test_artifact_equip_returns_updated_cabinet(client):
    from app.api.deps import require_auth
    from app.main import app

    equipped_artifact = {
        "id": "artifact_1",
        "card_code": "vault-key",
        "name": "Vault Key",
        "rarity": "rare",
        "family": "artifact",
        "description": "Equipable reward",
        "accent": "emerald",
        "item_category": "equipable",
        "is_equipped": True,
        "equip_slot": "profile_artifact",
        "equipped_at": "2026-03-25T12:00:00+00:00",
        "equipped_effect_summary": "Profile effect",
        "source_quest_id": "quest_1",
        "dropped_at": "2026-03-25T11:00:00+00:00",
    }
    cabinet = {
        "cosmetics": [],
        "collectibles": [],
        "equipable": [equipped_artifact],
        "total": 1,
    }

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        with patch("app.api.v1.endpoints.users.guild_card_service.equip_user_artifact", new=AsyncMock(return_value=equipped_artifact)) as mock_equip, \
             patch("app.api.v1.endpoints.users.guild_card_service.list_user_artifacts", new=AsyncMock(return_value=cabinet)) as mock_list:
            r = client.post("/api/v1/users/me/artifacts/artifact_1/equip")

        assert r.status_code == 200
        body = r.json()
        assert body["artifact"]["id"] == "artifact_1"
        assert body["artifact"]["is_equipped"] is True
        assert body["cabinet"]["total"] == 1
        mock_equip.assert_awaited_once()
        mock_list.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_artifact_equip_maps_value_error_to_400(client):
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        with patch(
            "app.api.v1.endpoints.users.guild_card_service.equip_user_artifact",
            new=AsyncMock(side_effect=ValueError("Only equipable artifacts can be equipped")),
        ):
            r = client.post("/api/v1/users/me/artifacts/artifact_1/equip")

        assert r.status_code == 400
        assert r.json()["detail"] == "Only equipable artifacts can be equipped"
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_artifact_unequip_returns_updated_cabinet(client):
    from app.api.deps import require_auth
    from app.main import app

    artifact = {
        "id": "artifact_1",
        "card_code": "vault-key",
        "name": "Vault Key",
        "rarity": "rare",
        "family": "artifact",
        "description": "Equipable reward",
        "accent": "emerald",
        "item_category": "equipable",
        "is_equipped": False,
        "equip_slot": None,
        "equipped_at": None,
        "equipped_effect_summary": "Profile effect",
        "source_quest_id": "quest_1",
        "dropped_at": "2026-03-25T11:00:00+00:00",
    }
    cabinet = {
        "cosmetics": [],
        "collectibles": [],
        "equipable": [artifact],
        "total": 1,
    }

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        with patch("app.api.v1.endpoints.users.guild_card_service.unequip_user_artifact", new=AsyncMock(return_value=artifact)) as mock_unequip, \
             patch("app.api.v1.endpoints.users.guild_card_service.list_user_artifacts", new=AsyncMock(return_value=cabinet)) as mock_list:
            r = client.post("/api/v1/users/me/artifacts/artifact_1/unequip")

        assert r.status_code == 200
        body = r.json()
        assert body["artifact"]["is_equipped"] is False
        assert body["cabinet"]["equipable"][0]["equip_slot"] is None
        mock_unequip.assert_awaited_once()
        mock_list.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Health and readiness probes
# ---------------------------------------------------------------------------


def test_health_is_pure_liveness_even_when_db_pool_missing(client):
    """/health must stay green even when readiness dependencies are unavailable."""
    with patch("app.db.session.pool", None), patch("app.main.get_redis_client", side_effect=RuntimeError("redis down")):
        r = client.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok", "message": "QuestionWork API is running"}


def test_ready_returns_503_when_db_pool_missing(client):
    """/ready must report dependency state and fail when DB is unavailable."""
    from app.main import _readiness_cache
    _readiness_cache["result"] = None
    with patch("app.db.session.pool", None), patch("app.main.get_redis_client", side_effect=RuntimeError("redis down")):
        r = client.get("/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["ready"] is False
    assert body["checks"]["db"] == "not initialized"
    assert body["checks"]["redis"] == "degraded"


def test_ready_keeps_redis_non_critical_in_development_when_db_is_ok(client):
    """Development readiness may stay green when DB is healthy but Redis is degraded."""
    from app.main import _readiness_cache
    _readiness_cache["result"] = None
    with (
        patch("app.db.session.pool", _MockPool()),
        patch("app.main.settings.APP_ENV", "development"),
        patch("app.main.settings.ADMIN_TOTP_REQUIRED", False),
        patch("app.main.get_redis_client", side_effect=RuntimeError("redis down")),
    ):
        r = client.get("/ready")

    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["redis"] == "degraded"
    assert body["shared_state"] == {
        "mode": "degraded-local-allowed",
        "redis_required": False,
        "status": "degraded",
    }


def test_ready_returns_503_when_non_development_requires_redis(client):
    """Non-development readiness must fail when Redis-backed shared state is unavailable."""
    from app.main import _readiness_cache
    _readiness_cache["result"] = None
    with (
        patch("app.db.session.pool", _MockPool()),
        patch("app.main.settings.APP_ENV", "staging"),
        patch("app.main.settings.ADMIN_TOTP_REQUIRED", False),
        patch("app.main.settings.REDIS_URL", "redis://example.invalid:6379/0"),
        patch("app.main.get_redis_client", side_effect=RuntimeError("redis down")),
    ):
        r = client.get("/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["ready"] is False
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["redis"] == "degraded"
    assert body["shared_state"] == {
        "mode": "redis-required",
        "redis_required": True,
        "status": "unavailable",
    }


def test_ready_returns_503_when_production_totp_requires_redis(client):
    """Production readiness must expose unavailable shared state when Redis is down."""
    from app.main import _readiness_cache
    _readiness_cache["result"] = None
    with (
        patch("app.db.session.pool", _MockPool()),
        patch("app.main.settings.APP_ENV", "production"),
        patch("app.main.settings.ADMIN_TOTP_REQUIRED", True),
        patch("app.main.settings.REDIS_URL", "redis://example.invalid:6379/0"),
        patch("app.main.get_redis_client", side_effect=RuntimeError("redis down")),
    ):
        r = client.get("/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["ready"] is False
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["redis"] == "degraded"
    assert body["shared_state"] == {
        "mode": "redis-required",
        "redis_required": True,
        "status": "unavailable",
    }


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


def test_get_quest_list_user_filter_requires_auth(client):
    """GET /quests/ with user_id must not allow anonymous personal filtering."""
    r = client.get("/api/v1/quests/?user_id=user_client")
    assert r.status_code == 403


def test_get_quest_list_user_filter_rejects_other_user(client):
    """Authenticated user cannot request another user's filtered quest list."""
    from app.main import app
    from app.api.deps import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _make_user("client")
    try:
        r = client.get("/api/v1/quests/?user_id=someone_else")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# GET /quests/{id} — quest detail
# ---------------------------------------------------------------------------


def test_get_quest_not_found(client):
    """GET /quests/{id} — mock DB returns None → 404."""
    r = client.get("/api/v1/quests/nonexistent-quest-id")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_get_quest_history_unauthenticated(client):
    """GET /quests/{id}/history without auth must not expose quest timeline."""
    with patch(
        "app.api.v1.endpoints.quests.quest_service.get_quest_status_history",
        new_callable=AsyncMock,
    ) as mock_history:
        mock_history.side_effect = PermissionError("Only quest participants or admins can view quest history")
        r = client.get("/api/v1/quests/some_id/history")
    assert r.status_code == 403


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
    r = client.post("/api/v1/quests/some_id/assign", json={"freelancer_id": "user_123"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /quests/{id}/start — auth guard
# ---------------------------------------------------------------------------


def test_start_quest_unauthenticated(client):
    """POST /quests/{id}/start without auth → 401."""
    r = client.post("/api/v1/quests/some_id/start")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /quests/{id}/complete — auth guard
# ---------------------------------------------------------------------------


def test_complete_quest_unauthenticated(client):
    """POST /quests/{id}/complete without auth → 401."""
    r = client.post("/api/v1/quests/some_id/complete")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /quests/{id}/request-revision — auth guard
# ---------------------------------------------------------------------------


def test_request_revision_unauthenticated(client):
    """POST /quests/{id}/request-revision without auth → 401."""
    r = client.post(
        "/api/v1/quests/some_id/request-revision",
        json={"revision_reason": "Пожалуйста, добавьте шаги запуска и поправьте README."},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /quests/{id}/confirm — auth guard
# ---------------------------------------------------------------------------


def test_confirm_quest_unauthenticated(client):
    """POST /quests/{id}/confirm without auth → 401."""
    r = client.post("/api/v1/quests/some_id/confirm")
    assert r.status_code == 401


def test_confirm_quest_returns_409_when_escrow_state_is_inconsistent(client):
    """Escrow mismatches must surface as operational conflicts, not bad requests."""
    from app.api.deps import require_auth
    from app.main import app
    from app.services.wallet_service import EscrowMismatchError

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        with patch(
            "app.api.v1.endpoints.quests.quest_service.confirm_quest_completion",
            new=AsyncMock(side_effect=EscrowMismatchError("Escrow hold amount does not match payout amount")),
        ):
            response = client.post("/api/v1/quests/some_id/confirm")

        assert response.status_code == 409
        assert response.json()["detail"] == "Quest payment state is inconsistent. Please contact support."
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.parametrize(
    ("path", "payload", "service_attr", "service_result", "expected_status", "user_role", "expected_action"),
    [
        (
            "/api/v1/quests/",
            {
                "title": "Valid title here",
                "description": "A sufficiently long description for the quest",
                "budget": 1000,
                "currency": "RUB",
            },
            "create_quest",
            _make_quest_payload(),
            201,
            "client",
            "create_quest",
        ),
        (
            "/api/v1/quests/some_id",
            {"title": "Updated quest title"},
            "update_quest",
            _make_quest_payload(),
            200,
            "client",
            "update_quest",
        ),
        (
            "/api/v1/quests/some_id/publish",
            None,
            "publish_quest",
            _make_quest_payload(status="open"),
            200,
            "client",
            "publish_quest",
        ),
        (
            "/api/v1/quests/some_id/apply",
            {"cover_letter": "Very interested in this quest, ready to start immediately."},
            "apply_to_quest",
            {
                "id": "app_1",
                "quest_id": "quest_test_1",
                "freelancer_id": "freelancer_test",
                "freelancer_username": "test_freelancer",
                "freelancer_grade": "novice",
                "cover_letter": "Very interested in this quest, ready to start immediately.",
                "proposed_price": "900.00",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            200,
            "freelancer",
            "apply_quest",
        ),
        (
            "/api/v1/quests/some_id/assign",
            {"freelancer_id": "user_123"},
            "assign_freelancer",
            _make_quest_payload(status="assigned"),
            200,
            "client",
            "assign_quest",
        ),
        (
            "/api/v1/quests/some_id/start",
            None,
            "start_quest",
            _make_quest_payload(status="in_progress"),
            200,
            "freelancer",
            "start_quest",
        ),
        (
            "/api/v1/quests/some_id/complete",
            {"delivery_note": "Implemented the requested feature and added tests."},
            "mark_quest_complete",
            (_make_quest_payload(status="completed"), 100),
            200,
            "freelancer",
            "complete_quest",
        ),
        (
            "/api/v1/quests/some_id/confirm",
            None,
            "confirm_quest_completion",
            {
                "message": "Quest confirmed",
                "quest": _make_quest_payload(status="confirmed"),
                "xp_reward": 100,
                "money_reward": "1000.00",
            },
            200,
            "client",
            "confirm_quest",
        ),
        (
            "/api/v1/quests/some_id/request-revision",
            {"revision_reason": "Пожалуйста, добавьте шаги запуска и поправьте README."},
            "request_quest_revision",
            _make_quest_payload(status="revision_requested"),
            200,
            "client",
            "request_quest_revision",
        ),
        (
            "/api/v1/quests/some_id/cancel",
            None,
            "cancel_quest",
            {
                "message": "Quest cancelled",
                "quest": _make_quest_payload(status="cancelled"),
            },
            200,
            "client",
            "cancel_quest",
        ),
    ],
)
def test_authenticated_quest_mutations_apply_user_scoped_rate_limit(
    client,
    monkeypatch,
    path,
    payload,
    service_attr,
    service_result,
    expected_status,
    user_role,
    expected_action,
):
    from app.api.deps import require_auth
    from app.api.v1.endpoints import quests as quest_endpoints
    from app.main import app

    ip_calls: list[tuple[str, str, int, int]] = []
    user_calls: list[tuple[str, str, int, int]] = []

    async def _fake_check_rate_limit(ip: str, action: str, limit: int, window_seconds: int):
        ip_calls.append((ip, action, limit, window_seconds))

    async def _fake_check_user_rate_limit(user_id: str, action: str, limit: int, window_seconds: int):
        user_calls.append((user_id, action, limit, window_seconds))

    async def _fake_service(*args, **kwargs):
        return service_result

    monkeypatch.setattr(quest_endpoints, "check_rate_limit", _fake_check_rate_limit)
    monkeypatch.setattr(quest_endpoints, "check_user_rate_limit", _fake_check_user_rate_limit)
    monkeypatch.setattr(quest_endpoints.quest_service, service_attr, _fake_service)

    app.dependency_overrides[require_auth] = lambda: _make_user(user_role)
    try:
        if path == "/api/v1/quests/some_id":
            response = client.patch(path, json=payload)
        else:
            response = client.post(path, json=payload) if payload is not None else client.post(path)

        assert response.status_code == expected_status
        assert len(ip_calls) == 1
        assert ip_calls[0][0]
        assert ip_calls[0][1:] == (expected_action, ip_calls[0][2], ip_calls[0][3])
        assert user_calls == [(f"{user_role}_test", expected_action, user_calls[0][2], user_calls[0][3])]
        assert ip_calls[0][2:] == user_calls[0][2:]
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Marketplace — public talent market and guild mutations
# ---------------------------------------------------------------------------


def test_marketplace_talent_is_public_and_returns_contract(client, monkeypatch):
    from app.api.v1.endpoints import marketplace as marketplace_endpoints

    async def _fake_talent_market(*args, **kwargs):
        return {
            "mode": "all",
            "summary": {
                "total_freelancers": 12,
                "solo_freelancers": 7,
                "guild_freelancers": 5,
                "total_guilds": 2,
                "top_solo_xp": 2100,
                "top_guild_rating": 980,
            },
            "members": [
                {
                    "id": "user_1",
                    "username": "solo_runner",
                    "level": 7,
                    "grade": "junior",
                    "xp": 2100,
                    "xp_to_next": 900,
                    "stats": {"int": 14, "dex": 12, "cha": 11},
                    "badges_count": 2,
                    "skills": ["python", "fastapi"],
                    "avg_rating": 4.9,
                    "review_count": 8,
                    "character_class": "berserk",
                    "market_kind": "solo",
                    "rank_score": 3456,
                    "guild": None,
                }
            ],
            "guilds": [
                {
                    "id": "guild_1",
                    "name": "Crimson Forge",
                    "slug": "crimson-forge",
                    "description": "Backend strike team",
                    "emblem": "ember",
                    "member_count": 5,
                    "member_limit": 20,
                    "total_xp": 8400,
                    "avg_rating": 4.8,
                    "confirmed_quests": 11,
                    "treasury_balance": "0.00",
                    "guild_tokens": 0,
                    "rating": 980,
                    "season_position": 1,
                    "top_skills": ["python", "postgres"],
                    "leader_username": "raid_lead",
                }
            ],
            "limit": 20,
            "offset": 0,
            "has_more": False,
            "generated_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(marketplace_endpoints.marketplace_service, "get_talent_market", _fake_talent_market)

    response = client.get("/api/v1/marketplace/talent?mode=all&sort_by=xp")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "all"
    assert body["summary"]["total_guilds"] == 2
    assert body["members"][0]["market_kind"] == "solo"
    assert body["guilds"][0]["name"] == "Crimson Forge"


def test_marketplace_guild_detail_is_public_and_returns_contract(client, monkeypatch):
    from app.api.v1.endpoints import marketplace as marketplace_endpoints

    async def _fake_guild_detail(*args, **kwargs):
        return {
            "guild": {
                "id": "guild_1",
                "name": "Crimson Forge",
                "slug": "crimson-forge",
                "description": "Backend strike team",
                "emblem": "ember",
                "member_count": 5,
                "member_limit": 20,
                "total_xp": 8400,
                "avg_rating": 4.8,
                "confirmed_quests": 11,
                "treasury_balance": "35.00",
                "guild_tokens": 3,
                "rating": 980,
                "season_position": 1,
                "top_skills": ["python", "postgres"],
                "leader_username": "raid_lead",
            },
            "members": [
                {
                    "id": "user_1",
                    "username": "raid_lead",
                    "level": 7,
                    "grade": "junior",
                    "xp": 2100,
                    "xp_to_next": 900,
                    "stats": {"int": 14, "dex": 12, "cha": 11},
                    "skills": ["python", "fastapi"],
                    "avg_rating": 4.9,
                    "review_count": 8,
                    "character_class": "berserk",
                    "role": "leader",
                    "contribution": 610,
                    "joined_at": datetime.now(timezone.utc),
                }
            ],
            "activity": [
                {
                    "id": "gact_1",
                    "event_type": "quest_confirmed",
                    "summary": "Quest confirmation added treasury and tokens",
                    "actor_user_id": "user_1",
                    "actor_username": "raid_lead",
                    "quest_id": "quest_1",
                    "treasury_delta": "35.00",
                    "guild_tokens_delta": 3,
                    "contribution_delta": 610,
                    "created_at": datetime.now(timezone.utc),
                }
            ],
            "trophies": [
                {
                    "id": "gcard_1",
                    "card_code": "storm-banner",
                    "name": "Storm Banner",
                    "rarity": "rare",
                    "family": "banner",
                    "description": "Rare reward",
                    "accent": "cyan",
                    "awarded_to_user_id": "user_1",
                    "awarded_to_username": "raid_lead",
                    "source_quest_id": "quest_1",
                    "dropped_at": datetime.now(timezone.utc),
                }
            ],
            "seasonal_sets": [
                {
                    "family": "banner",
                    "label": "Storm Banners",
                    "accent": "cyan",
                    "season_code": "forge-awakening",
                    "target_cards": 4,
                    "collected_cards": 1,
                    "missing_cards": 3,
                    "progress_percent": 25,
                    "completed": False,
                    "rarity": "rare",
                    "reward_label": "Storm campaign reserve",
                    "reward_treasury_bonus": "40.00",
                    "reward_guild_tokens_bonus": 3,
                    "reward_badge_name": "Storm Standard",
                    "reward_claimed": False,
                    "reward_claimed_at": None,
                }
            ],
            "progression_snapshot": {
                "season_code": "2026-S1",
                "seasonal_xp": 6400,
                "current_tier": "silver",
                "next_tier": "gold",
                "next_tier_xp": 20000,
                "xp_to_next_tier": 13600,
                "progress_percent": 9,
                "xp_bonus_percent": 5,
                "tier_benefits": ["+5% XP"],
                "season_rank": 2,
                "completed_sets": 0,
                "total_sets": 1,
                "claimed_rewards": 0,
                "leaderboard": [
                    {
                        "rank": 1,
                        "member": {
                            "id": "user_1",
                            "username": "raid_lead",
                            "level": 7,
                            "grade": "junior",
                            "xp": 2100,
                            "xp_to_next": 900,
                            "stats": {"int": 14, "dex": 12, "cha": 11},
                            "skills": ["python", "fastapi"],
                            "avg_rating": 4.9,
                            "review_count": 8,
                            "character_class": "berserk",
                            "role": "leader",
                            "contribution": 610,
                            "joined_at": datetime.now(timezone.utc),
                        },
                        "trophy_count": 1,
                        "family_label": "banner",
                    }
                ],
            },
            "badges": [
                {
                    "id": "gbadge_1",
                    "badge_code": "forge-awakening:banner",
                    "name": "Storm Standard",
                    "slug": "storm-standard",
                    "accent": "cyan",
                    "season_code": "forge-awakening",
                    "family": "banner",
                    "awarded_at": datetime.now(timezone.utc),
                }
            ],
            "generated_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(marketplace_endpoints.marketplace_service, "get_guild_public_profile", _fake_guild_detail)

    response = client.get("/api/v1/marketplace/guilds/crimson-forge")

    assert response.status_code == 200
    body = response.json()
    assert body["guild"]["slug"] == "crimson-forge"
    assert body["members"][0]["role"] == "leader"
    assert body["activity"][0]["event_type"] == "quest_confirmed"
    assert body["trophies"][0]["card_code"] == "storm-banner"
    assert body["seasonal_sets"][0]["family"] == "banner"
    assert body["progression_snapshot"]["leaderboard"][0]["rank"] == 1
    assert body["progression_snapshot"]["completed_sets"] == 0
    assert body["progression_snapshot"]["current_tier"] == "silver"
    assert body["badges"][0]["slug"] == "storm-standard"


def test_create_guild_client_forbidden(client):
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        response = client.post(
            "/api/v1/marketplace/guilds",
            json={"name": "Client Guild", "description": "Should fail", "emblem": "ember"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_quest_recommended_freelancers_returns_contract(client, monkeypatch):
    from app.api.v1.endpoints import quests as quests_endpoints

    async def _fake_get_quest_by_id(conn, quest_id, current_user=None):
        return True

    async def _fake_match_freelancers_for_quest(conn, quest_id, limit=10):
        return {
            "quest_id": quest_id,
            "recommendations": [
                {
                    "freelancer": {
                        "id": "freelancer_1",
                        "username": "freelancer_1",
                        "level": 6,
                        "grade": "middle",
                        "xp": 1200,
                        "xp_to_next": 300,
                        "stats": {"int": 13, "dex": 11, "cha": 10},
                        "skills": ["python", "fastapi"],
                        "avg_rating": 4.9,
                        "review_count": 9,
                        "trust_score": 0.88,
                        "typical_budget_band": "15k_to_50k",
                        "availability_status": "available",
                        "response_time_hint": "Обычно отвечает в течение рабочего дня",
                        "character_class": None,
                        "avatar_url": None,
                    },
                    "match_score": 0.91,
                    "match_breakdown": {
                        "skill_overlap": 1.0,
                        "grade_fit": 1.0,
                        "trust_score": 0.88,
                        "availability": 1.0,
                        "budget_fit": 1.0,
                    },
                    "matched_skills": ["python", "fastapi"],
                }
            ],
            "generated_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(quests_endpoints.quest_service, "get_quest_by_id", _fake_get_quest_by_id)
    monkeypatch.setattr(quests_endpoints.matching_service, "match_freelancers_for_quest", _fake_match_freelancers_for_quest)

    response = client.get("/api/v1/quests/quest_1/recommended-freelancers?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["quest_id"] == "quest_1"
    assert body["recommendations"][0]["freelancer"]["id"] == "freelancer_1"
    assert body["recommendations"][0]["matched_skills"] == ["python", "fastapi"]


def test_users_me_recommended_quests_requires_freelancer_role(client):
    from app.main import app
    from app.api.deps import require_auth

    app.dependency_overrides[require_auth] = lambda: _make_user("client")

    try:
        response = client.get("/api/v1/users/me/recommended-quests")
    finally:
        app.dependency_overrides.pop(require_auth, None)

    assert response.status_code == 403
    assert response.json()["detail"] == "Only freelancers can access recommended quests"


def test_users_me_player_cards_returns_empty_for_non_freelancer(client):
    from app.main import app
    from app.api.deps import require_auth

    app.dependency_overrides[require_auth] = lambda: _make_user("client")

    try:
        response = client.get("/api/v1/users/me/player-cards")
    finally:
        app.dependency_overrides.pop(require_auth, None)

    assert response.status_code == 200
    assert response.json()["drops"] == []
    assert response.json()["total"] == 0


def test_users_me_player_cards_returns_empty_when_table_missing(client):
    from app.main import app
    from app.api.deps import require_auth
    from app.db.session import get_db_connection

    class _MissingPlayerCardsConn(_MockConn):
        async def fetch(self, *args, **kwargs):
            raise asyncpg.UndefinedTableError('relation "player_card_drops" does not exist')

    async def _missing_table_dep():
        yield _MissingPlayerCardsConn()

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    app.dependency_overrides[get_db_connection] = _missing_table_dep

    try:
        response = client.get("/api/v1/users/me/player-cards")
    finally:
        app.dependency_overrides.pop(require_auth, None)
        app.dependency_overrides[get_db_connection] = _mock_conn_dep

    assert response.status_code == 200
    assert response.json()["drops"] == []
    assert response.json()["total"] == 0


def test_users_me_recommended_quests_returns_contract(client, monkeypatch):
    from app.main import app
    from app.api.deps import require_auth
    from app.api.v1.endpoints import users as users_endpoints

    async def _fake_recommend_quests_for_user(conn, user_id, limit=10):
        now = datetime.now(timezone.utc)
        return {
            "user_id": user_id,
            "recommendations": [
                {
                    "quest": {
                        **_make_quest_payload(),
                        "id": "quest_recommended",
                        "title": "Recommended backend quest",
                        "skills": ["python", "fastapi"],
                    },
                    "match_score": 0.87,
                    "match_breakdown": {
                        "skill_overlap": 1.0,
                        "grade_fit": 1.0,
                        "trust_score": 0.8,
                        "availability": 1.0,
                        "budget_fit": 0.7,
                    },
                    "matched_skills": ["python", "fastapi"],
                }
            ],
            "generated_at": now,
        }

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    monkeypatch.setattr(users_endpoints.matching_service, "recommend_quests_for_user", _fake_recommend_quests_for_user)

    try:
        response = client.get("/api/v1/users/me/recommended-quests?limit=4")
    finally:
        app.dependency_overrides.pop(require_auth, None)

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "freelancer_test"
    assert body["recommendations"][0]["quest"]["id"] == "quest_recommended"
    assert body["recommendations"][0]["matched_skills"] == ["python", "fastapi"]


def test_create_guild_freelancer_applies_rate_limit_and_returns_result(client, monkeypatch):
    from app.api.deps import require_auth
    from app.api.v1.endpoints import marketplace as marketplace_endpoints
    from app.main import app

    rate_limit_calls: list[tuple[str, str, int, int]] = []

    async def _fake_check_rate_limit(ip: str, action: str, limit: int, window_seconds: int):
        rate_limit_calls.append((ip, action, limit, window_seconds))

    async def _fake_create_guild(conn, current_user, body):
        return {
            "guild_id": "guild_new_1",
            "status": "created",
            "message": f"Guild {body.name} created",
        }

    monkeypatch.setattr(marketplace_endpoints, "check_rate_limit", _fake_check_rate_limit)
    monkeypatch.setattr(marketplace_endpoints.marketplace_service, "create_guild", _fake_create_guild)

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        response = client.post(
            "/api/v1/marketplace/guilds",
            json={"name": "Crimson Forge", "description": "Backend raid squad", "emblem": "ember"},
        )

        assert response.status_code == 200
        assert response.json()["guild_id"] == "guild_new_1"
        assert rate_limit_calls == [(rate_limit_calls[0][0], "create_guild", 5, 3600)]
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.parametrize(
    ("path", "action", "limit", "service_name", "payload"),
    [
        (
            "/api/v1/marketplace/guilds",
            "create_guild",
            5,
            "create_guild",
            {"name": "Crimson Forge", "description": "Backend raid squad", "emblem": "ember"},
        ),
        (
            "/api/v1/marketplace/guilds/guild_1/join",
            "join_guild",
            10,
            "join_guild",
            None,
        ),
        (
            "/api/v1/marketplace/guilds/guild_1/leave",
            "leave_guild",
            10,
            "leave_guild",
            None,
        ),
    ],
)
def test_marketplace_guild_mutations_use_proxy_aware_ip(client, monkeypatch, path, action, limit, service_name, payload):
    from app.api.deps import require_auth
    from app.api.v1.endpoints import marketplace as marketplace_endpoints
    from app.main import app

    rate_limit_calls: list[tuple[str, str, int, int]] = []

    async def _fake_check_rate_limit(ip: str, action: str, limit: int, window_seconds: int):
        rate_limit_calls.append((ip, action, limit, window_seconds))

    async def _fake_guild_action(*args, **kwargs):
        return {
            "guild_id": "guild_new_1",
            "status": "ok",
            "message": "guild action applied",
        }

    monkeypatch.setattr(marketplace_endpoints, "check_rate_limit", _fake_check_rate_limit)
    monkeypatch.setattr(marketplace_endpoints, "get_client_ip", lambda request: "203.0.113.42")
    monkeypatch.setattr(marketplace_endpoints.marketplace_service, service_name, _fake_guild_action)

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        response = client.post(path, json=payload)

        assert response.status_code == 200
        assert response.json()["guild_id"] == "guild_new_1"
        assert rate_limit_calls == [("203.0.113.42", action, limit, 3600)]
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Reviews — auth guards
# ---------------------------------------------------------------------------


def test_create_review_unauthenticated(client):
    """POST /reviews/ without auth → 401."""
    r = client.post(
        "/api/v1/reviews/",
        json={
            "quest_id": "some_id",
            "reviewee_id": "user_123",
            "rating": 5,
            "comment": "Отличная работа и быстрая коммуникация.",
        },
    )
    assert r.status_code == 401


def test_check_review_status_unauthenticated(client):
    """GET /reviews/check/{quest_id} without auth → 401."""
    r = client.get("/api/v1/reviews/check/some_id")
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


def test_get_messages_unauthenticated(client):
    """GET /messages/{quest_id} without auth → 401."""
    r = client.get("/api/v1/messages/some_id")
    assert r.status_code == 401


def test_list_dialogs_unauthenticated(client):
    """GET /messages/dialogs without auth → 401."""
    r = client.get("/api/v1/messages/dialogs")
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


# ---------------------------------------------------------------------------
# P1 A-01: Banned user must not log in
# ---------------------------------------------------------------------------


def test_login_banned_user_returns_403(client):
    """P1 A-01: Banned user attempting /login must get 403."""
    from unittest.mock import patch as _patch
    from app.main import app
    from app.db.session import get_db_connection

    banned_user_row = {
        "id": "user_banned_login",
        "username": "banned_login_guy",
        "email": "banned_login@test.com",
        "password_hash": "$2b$12$fake_hash",
        "role": "freelancer",
        "is_banned": True,
        "banned_reason": "TOS violation",
        "level": 1,
        "grade": "novice",
        "xp": 0,
        "xp_to_next": 100,
        "stat_points": 0,
        "stats_int": 10,
        "stats_dex": 10,
        "stats_cha": 10,
        "badges": "[]",
        "bio": None,
        "skills": "[]",
        "character_class": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    class _BannedLoginConn(_MockConn):
        async def fetchrow(self, *a, **kw):
            return banned_user_row

    async def _banned_login_conn():
        yield _BannedLoginConn()

    app.dependency_overrides[get_db_connection] = _banned_login_conn
    try:
        with _patch("app.api.v1.endpoints.auth.verify_password", return_value=True):
            r = client.post(
                "/api/v1/auth/login",
                json={"username": "banned_login_guy", "password": "SecurePass1!"},
            )
        assert r.status_code == 403
        assert "banned" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides[get_db_connection] = _mock_conn_dep


def test_register_returns_503_when_refresh_store_is_unavailable(client):
    from unittest.mock import patch as _patch, AsyncMock
    from app.api.v1.endpoints import auth as auth_module

    error_cls = getattr(
        auth_module,
        "RefreshTokenStoreUnavailableError",
        type("RefreshTokenStoreUnavailableError", (RuntimeError,), {}),
    )

    with _patch(
        "app.api.v1.endpoints.auth.create_refresh_token",
        new=AsyncMock(side_effect=error_cls("refresh store unavailable")),
    ):
        r = client.post(
            "/api/v1/auth/register",
            json={
                "username": "register_503_user",
                "email": "register503@test.com",
                "password": "SecurePass1!",
            },
        )

    assert r.status_code == 503
    assert r.json()["detail"] == "Authentication service temporarily unavailable"


def test_login_returns_503_when_refresh_store_is_unavailable(client):
    from unittest.mock import patch as _patch, AsyncMock
    from app.main import app
    from app.db.session import get_db_connection
    from app.api.v1.endpoints import auth as auth_module

    error_cls = getattr(
        auth_module,
        "RefreshTokenStoreUnavailableError",
        type("RefreshTokenStoreUnavailableError", (RuntimeError,), {}),
    )

    user_row = {
        "id": "user_login_503",
        "username": "login_503_user",
        "email": "login503@test.com",
        "password_hash": "$2b$12$fake_hash",
        "role": "freelancer",
        "is_banned": False,
        "level": 1,
        "grade": "novice",
        "xp": 0,
        "xp_to_next": 100,
        "stat_points": 0,
        "stats_int": 10,
        "stats_dex": 10,
        "stats_cha": 10,
        "badges": "[]",
        "bio": None,
        "skills": "[]",
        "character_class": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    class _Login503Conn(_MockConn):
        async def fetchrow(self, *a, **kw):
            return user_row

    async def _login_503_conn():
        yield _Login503Conn()

    app.dependency_overrides[get_db_connection] = _login_503_conn
    try:
        with _patch("app.api.v1.endpoints.auth.verify_password", return_value=True), _patch(
            "app.api.v1.endpoints.auth.create_refresh_token",
            new=AsyncMock(side_effect=error_cls("refresh store unavailable")),
        ):
            r = client.post(
                "/api/v1/auth/login",
                json={"username": "login_503_user", "password": "SecurePass1!"},
            )

        assert r.status_code == 503
        assert r.json()["detail"] == "Authentication service temporarily unavailable"
    finally:
        app.dependency_overrides[get_db_connection] = _mock_conn_dep


def test_refresh_returns_503_when_refresh_store_is_unavailable(client):
    from unittest.mock import patch as _patch
    from app.api.v1.endpoints import auth as auth_module

    error_cls = getattr(
        auth_module,
        "RefreshTokenStoreUnavailableError",
        type("RefreshTokenStoreUnavailableError", (RuntimeError,), {}),
    )

    with _patch(
        "app.api.v1.endpoints.auth.rotate_refresh_token",
        side_effect=error_cls("refresh store unavailable"),
    ):
        client.cookies.set("refresh_token", "refresh_503_token")
        r = client.post("/api/v1/auth/refresh")

    client.cookies.clear()

    assert r.status_code == 503
    assert r.json()["detail"] == "Authentication service temporarily unavailable"


def test_logout_returns_503_when_refresh_store_is_unavailable(client):
    from unittest.mock import patch as _patch
    from app.api.v1.endpoints import auth as auth_module

    error_cls = getattr(
        auth_module,
        "RefreshTokenStoreUnavailableError",
        type("RefreshTokenStoreUnavailableError", (RuntimeError,), {}),
    )

    with _patch(
        "app.api.v1.endpoints.auth.revoke_refresh_token",
        side_effect=error_cls("refresh store unavailable"),
    ):
        client.cookies.set("refresh_token", "logout_503_token")
        r = client.post("/api/v1/auth/logout")

    client.cookies.clear()

    assert r.status_code == 503
    assert r.json()["detail"] == "Authentication service temporarily unavailable"


def test_get_world_meta_contract(client):
    from app.main import app
    from app.db.session import get_db_connection

    class _MetaConn(_MockConn):
        async def fetchrow(self, *a, **kw):
            return {
                "total_users": 12,
                "freelancer_count": 7,
                "client_count": 4,
                "open_quests": 5,
                "in_progress_quests": 3,
                "revision_requested_quests": 1,
                "urgent_quests": 2,
                "confirmed_quests_week": 6,
                "unread_notifications": 9,
                "total_reviews": 14,
                "avg_rating": 4.8,
                "earned_badges": 11,
            }

    async def _meta_conn():
        yield _MetaConn()

    app.dependency_overrides[get_db_connection] = _meta_conn
    try:
        r = client.get("/api/v1/meta/world")
        assert r.status_code == 200
        data = r.json()
        assert data["metrics"]["total_users"] == 12
        assert data["season"]["title"]
        assert len(data["factions"]) == 3
        assert data["community"]["target_label"] == "weekly confirmed quests"
        assert len(data["trends"]) == 3
        assert data["trends"][0]["direction"] in {"rising", "falling", "steady"}
        assert "points" in data["trends"][0]
    finally:
        app.dependency_overrides[get_db_connection] = _mock_conn_dep


# ---------------------------------------------------------------------------
# P1 A-02: Public profile strips email
# ---------------------------------------------------------------------------


def test_get_user_profile_strips_email(client):
    """P1 A-02: Public GET /users/{id} must not leak private fields."""
    from app.main import app
    from app.db.session import get_db_connection

    user_row = {
        "id": "user_pub1",
        "username": "public_user",
        "email": "secret@private.com",
        "role": "freelancer",
        "is_banned": False,
        "banned_reason": None,
        "level": 5,
        "grade": "junior",
        "xp": 600,
        "xp_to_next": 1400,
        "stat_points": 0,
        "stats_int": 10,
        "stats_dex": 10,
        "stats_cha": 10,
        "badges": "[]",
        "bio": None,
        "skills": "[]",
        "character_class": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    class _UserConn(_MockConn):
        async def fetchrow(self, *a, **kw):
            return user_row

    async def _user_conn():
        yield _UserConn()

    app.dependency_overrides[get_db_connection] = _user_conn
    try:
        r = client.get("/api/v1/users/user_pub1")
        assert r.status_code == 200
        data = r.json()
        assert "email" not in data, "Public profile must not expose email"
        assert "is_banned" not in data, "Public profile must not expose moderation status"
        assert "banned_reason" not in data, "Public profile must not expose moderation reason"
        assert data["username"] == "public_user"
    finally:
        app.dependency_overrides[get_db_connection] = _mock_conn_dep
