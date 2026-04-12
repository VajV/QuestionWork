from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest


class _MockConn:
    async def fetchrow(self, *args, **kwargs):
        return None

    async def fetch(self, *args, **kwargs):
        return []

    async def fetchval(self, *args, **kwargs):
        return 0


async def _mock_conn_dep():
    yield _MockConn()


def _make_user(role="client"):
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


def test_quest_invite_route_requires_auth(client):
    response = client.post(
        "/api/v1/quests/quest_123/invite",
        json={"freelancer_id": "user_fl"},
    )
    assert response.status_code == 401


def test_quest_invite_route_success(client):
    from app.api.deps import require_auth
    from app.main import app

    expected = {
        "quest_id": "quest_123",
        "freelancer_id": "user_fl",
        "already_sent": False,
        "message": "Invite sent to freelancer",
    }

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        with patch(
            "app.api.v1.endpoints.quests.quest_service.invite_freelancer_to_quest",
            new=AsyncMock(return_value=expected),
        ):
            response = client.post(
                "/api/v1/quests/quest_123/invite",
                json={"freelancer_id": "user_fl"},
            )

        assert response.status_code == 200
        assert response.json() == expected
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_quest_invite_route_returns_400_on_invalid_state(client):
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("client")
    try:
        with patch(
            "app.api.v1.endpoints.quests.quest_service.invite_freelancer_to_quest",
            new=AsyncMock(side_effect=ValueError("This freelancer has already applied to the quest")),
        ):
            response = client.post(
                "/api/v1/quests/quest_123/invite",
                json={"freelancer_id": "user_fl"},
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "This freelancer has already applied to the quest"
    finally:
        app.dependency_overrides.pop(require_auth, None)