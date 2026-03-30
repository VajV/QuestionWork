from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _make_user():
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats

    return UserProfile(
        id="user_avatar_1",
        username="avatarhero",
        email="avatarhero@example.com",
        role=UserRoleEnum.freelancer,
        level=4,
        grade=GradeEnum.novice,
        xp=200,
        xp_to_next=250,
        stats=UserStats(int=10, dex=11, cha=9),
        badges=[],
        bio="Avatar ready profile",
        skills=["FastAPI"],
        availability_status="available",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _profile_row(avatar_url: str | None):
    now = datetime.now(timezone.utc)
    return {
        "id": "user_avatar_1",
        "username": "avatarhero",
        "email": "avatarhero@example.com",
        "role": "freelancer",
        "is_banned": False,
        "banned_reason": None,
        "level": 4,
        "grade": "novice",
        "xp": 200,
        "xp_to_next": 250,
        "stat_points": 0,
        "stats_int": 10,
        "stats_dex": 11,
        "stats_cha": 9,
        "badges": [],
        "bio": "Avatar ready profile",
        "avatar_url": avatar_url,
        "skills": ["FastAPI"],
        "availability_status": "available",
        "portfolio_links": [],
        "portfolio_summary": None,
        "onboarding_completed": False,
        "onboarding_completed_at": None,
        "profile_completeness_percent": 40,
        "character_class": None,
        "created_at": now,
        "updated_at": now,
    }


class _AsyncTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(scope="module")
def client():
    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
    ):
        from app.main import app
        from app.db.session import get_db_connection
        from fastapi.testclient import TestClient

        async def _mock_conn_dep():
            conn = AsyncMock()
            conn.transaction = lambda: _AsyncTransaction()
            conn.fetchrow = AsyncMock(return_value=_profile_row(None))
            return conn

        app.dependency_overrides[get_db_connection] = _mock_conn_dep

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.pop(get_db_connection, None)


def test_upload_avatar_requires_auth(client):
    resp = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.png", b"fake", "image/png")},
    )
    assert resp.status_code == 401


def test_upload_avatar_rejects_non_image_files(client, tmp_path):
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user()
    try:
        with patch("app.api.v1.endpoints.users.AVATAR_UPLOAD_DIR", tmp_path / "avatars"):
            resp = client.post(
                "/api/v1/users/me/avatar",
                files={"file": ("avatar.txt", b"not-an-image", "text/plain")},
            )
        assert resp.status_code == 400
        assert resp.json()["detail"] in {
            "Unsupported avatar file extension",
            "Unsupported avatar file type",
        }
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_upload_avatar_returns_public_path_and_updates_user(client, tmp_path):
    from app.api.deps import require_auth
    from app.main import app
    from app.db.session import get_db_connection

    upload_root = tmp_path / "avatars"
    conn = AsyncMock()
    conn.transaction = lambda: _AsyncTransaction()
    conn.fetchrow = AsyncMock(return_value=_profile_row("/uploads/avatars/generated.png"))

    async def _mock_conn_dep():
        return conn

    app.dependency_overrides[require_auth] = lambda: _make_user()
    app.dependency_overrides[get_db_connection] = _mock_conn_dep
    try:
        with patch("app.api.v1.endpoints.users.AVATAR_UPLOAD_DIR", upload_root):
            resp = client.post(
                "/api/v1/users/me/avatar",
                files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\nsmall-image", "image/png")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["avatar_url"].startswith("/uploads/avatars/")
        saved_files = list(upload_root.glob("*.png"))
        assert len(saved_files) == 1
        assert conn.fetchrow.await_count == 1
        assert body["avatar_url"] == conn.fetchrow.await_args.args[1]
    finally:
        app.dependency_overrides.pop(require_auth, None)
        app.dependency_overrides.pop(get_db_connection, None)


def test_upload_avatar_rate_limits_requests(client, tmp_path):
    from fastapi import HTTPException

    from app.api.deps import require_auth
    from app.main import app
    from app.db.session import get_db_connection

    conn = AsyncMock()
    conn.transaction = lambda: _AsyncTransaction()

    async def _mock_conn_dep():
        return conn

    app.dependency_overrides[require_auth] = lambda: _make_user()
    app.dependency_overrides[get_db_connection] = _mock_conn_dep
    try:
        with (
            patch("app.api.v1.endpoints.users.AVATAR_UPLOAD_DIR", tmp_path / "avatars"),
            patch(
                "app.api.v1.endpoints.users.check_rate_limit",
                new=AsyncMock(side_effect=HTTPException(status_code=429, detail="Too many requests")),
            ),
        ):
            resp = client.post(
                "/api/v1/users/me/avatar",
                files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\nsmall-image", "image/png")},
            )

        assert resp.status_code == 429
        assert resp.json()["detail"] == "Too many requests"
    finally:
        app.dependency_overrides.pop(require_auth, None)
        app.dependency_overrides.pop(get_db_connection, None)