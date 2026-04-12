from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class _MockConn:
    async def fetchrow(self, *args, **kwargs):
        return None

    async def fetch(self, *args, **kwargs):
        return []

    async def fetchval(self, *args, **kwargs):
        return 0


async def _mock_conn_dep():
    yield _MockConn()


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


ADMIN_RUNTIME_ROUTES = [
    ("GET", "/api/v1/admin/commands/00000000-0000-0000-0000-000000000001"),
    ("GET", "/api/v1/admin/jobs/00000000-0000-0000-0000-000000000002"),
    ("POST", "/api/v1/admin/jobs/00000000-0000-0000-0000-000000000002/requeue"),
    ("GET", "/api/v1/admin/operations"),
    ("GET", "/api/v1/admin/runtime/heartbeats"),
    ("POST", "/api/v1/admin/runtime/heartbeats/prune"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_RUNTIME_ROUTES)
def test_admin_runtime_routes_require_auth(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401


def test_admin_get_command_status_success(client):
    from app.api.deps import require_admin
    from app.main import app

    expected = {
        "id": "00000000-0000-0000-0000-000000000001",
        "command_kind": "admin.force-complete",
        "status": "succeeded",
        "dedupe_key": "cmd-1",
        "requested_by_user_id": None,
        "requested_by_admin_id": "admin_1",
        "request_ip": "127.0.0.1",
        "request_user_agent": "pytest",
        "request_id": "req-1",
        "trace_id": "trace-1",
        "payload_json": {"quest_id": "quest_1"},
        "result_json": {"ok": True},
        "error_code": None,
        "error_text": None,
        "submitted_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "jobs": [
            {
                "id": "00000000-0000-0000-0000-000000000010",
                "kind": "admin.force-complete",
                "queue_name": "default",
                "status": "succeeded",
                "attempt_count": 1,
                "max_attempts": 3,
                "queue_publish_attempts": 1,
                "scheduled_for": datetime.now(timezone.utc),
                "available_at": datetime.now(timezone.utc),
                "enqueued_at": datetime.now(timezone.utc),
                "started_at": datetime.now(timezone.utc),
                "finished_at": datetime.now(timezone.utc),
                "last_heartbeat_at": datetime.now(timezone.utc),
                "last_error_code": None,
                "last_error": None,
            }
        ],
    }

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        with patch(
            "app.api.v1.endpoints.admin_runtime.admin_runtime_service.get_command_status",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/v1/admin/commands/00000000-0000-0000-0000-000000000001")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == expected["id"]
        assert body["status"] == "succeeded"
        assert body["jobs"][0]["status"] == "succeeded"
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_admin_get_job_status_returns_404_when_missing(client):
    from app.api.deps import require_admin
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        with patch(
            "app.api.v1.endpoints.admin_runtime.admin_runtime_service.get_job_status",
            new=AsyncMock(return_value=None),
        ):
            response = client.get("/api/v1/admin/jobs/00000000-0000-0000-0000-000000000002")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_admin_requeue_job_success(client):
    from app.api.deps import require_admin
    from app.main import app

    expected = {
        "job_id": "00000000-0000-0000-0000-000000000002",
        "previous_status": "dead_letter",
        "status": "retry_scheduled",
        "queue_name": "ops",
        "enqueued": True,
        "message": "Job requeued and published to the worker queue",
        "enqueue_error": None,
    }

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        with patch(
            "app.api.v1.endpoints.admin_runtime.admin_runtime_service.requeue_job",
            new=AsyncMock(return_value=expected),
        ):
            response = client.post(
                "/api/v1/admin/jobs/00000000-0000-0000-0000-000000000002/requeue",
                json={"reason": "recover after provider fix"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "retry_scheduled"
        assert body["enqueued"] is True
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_admin_requeue_job_returns_400_on_invalid_status(client):
    from app.api.deps import require_admin
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        with patch(
            "app.api.v1.endpoints.admin_runtime.admin_runtime_service.requeue_job",
            new=AsyncMock(side_effect=ValueError("Only failed or dead-letter jobs can be requeued manually")),
        ):
            response = client.post(
                "/api/v1/admin/jobs/00000000-0000-0000-0000-000000000002/requeue",
                json={},
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "Only failed or dead-letter jobs can be requeued manually"
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_admin_requeue_job_accepts_missing_body(client):
    from app.api.deps import require_admin
    from app.main import app

    expected = {
        "job_id": "00000000-0000-0000-0000-000000000002",
        "previous_status": "dead_letter",
        "status": "retry_scheduled",
        "queue_name": "ops",
        "enqueued": False,
        "message": "Job requeued; scheduler will retry enqueue automatically",
        "enqueue_error": "redis unavailable",
    }

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        with patch(
            "app.api.v1.endpoints.admin_runtime.admin_runtime_service.requeue_job",
            new=AsyncMock(return_value=expected),
        ):
            response = client.post(
                "/api/v1/admin/jobs/00000000-0000-0000-0000-000000000002/requeue",
            )

        assert response.status_code == 200
        assert response.json()["enqueued"] is False
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_admin_list_operations_success(client):
    from app.api.deps import require_admin
    from app.main import app

    expected = {
        "items": [
            {
                "command_id": "00000000-0000-0000-0000-000000000001",
                "job_id": "00000000-0000-0000-0000-000000000010",
                "action": "admin.force-complete",
                "command_status": "running",
                "job_kind": "admin.force-complete",
                "job_status": "queued",
                "actor_admin_id": "admin_1",
                "actor_user_id": None,
                "queue_name": "default",
                "request_id": "req-1",
                "trace_id": "trace-1",
                "submitted_at": datetime.now(timezone.utc),
                "started_at": None,
                "finished_at": None,
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 50,
        "has_more": False,
    }

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        with patch(
            "app.api.v1.endpoints.admin_runtime.admin_runtime_service.list_operations",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/v1/admin/operations", params={"status": "queued", "actor": "admin_1"})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["action"] == "admin.force-complete"
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_admin_list_runtime_heartbeats_success(client):
    from app.api.deps import require_admin
    from app.main import app

    expected = {
        "generated_at": datetime.now(timezone.utc),
        "active_only": True,
        "total": 2,
        "stale_total": 1,
        "active_workers": 1,
        "active_schedulers": 1,
        "stale_workers": 1,
        "stale_schedulers": 0,
        "leader_runtime_id": "host:123",
        "leader_count": 1,
        "runtimes": [
            {
                "id": "00000000-0000-0000-0000-000000000101",
                "runtime_kind": "scheduler",
                "runtime_id": "host:123",
                "hostname": "host",
                "pid": 123,
                "started_at": datetime.now(timezone.utc),
                "last_seen_at": datetime.now(timezone.utc),
                "meta_json": {"poll_interval_seconds": 5},
                "queue_name": None,
                "heartbeat_interval_seconds": 10,
                "stale_after_seconds": 30,
                "started_age_seconds": 12,
                "seconds_since_last_seen": 2,
                "is_stale": False,
                "is_leader": True,
                "lease_ttl_seconds": 30,
                "lease_expires_in_seconds": 28,
            },
            {
                "id": "00000000-0000-0000-0000-000000000102",
                "runtime_kind": "worker",
                "runtime_id": "host:456",
                "hostname": "host",
                "pid": 456,
                "started_at": datetime.now(timezone.utc),
                "last_seen_at": datetime.now(timezone.utc),
                "meta_json": {"queue_names": ["default", "ops"]},
                "queue_name": "ops",
                "heartbeat_interval_seconds": 15,
                "stale_after_seconds": 30,
                "started_age_seconds": 44,
                "seconds_since_last_seen": 99,
                "is_stale": True,
                "is_leader": None,
                "lease_ttl_seconds": None,
                "lease_expires_in_seconds": None,
            },
        ],
    }

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        with patch(
            "app.api.v1.endpoints.admin_runtime.admin_runtime_service.list_runtime_heartbeats",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/v1/admin/runtime/heartbeats", params={"runtime_kind": "worker"})

        assert response.status_code == 200
        body = response.json()
        assert body["active_only"] is True
        assert body["total"] == 2
        assert body["stale_total"] == 1
        assert body["active_schedulers"] == 1
        assert body["leader_runtime_id"] == "host:123"
        assert body["runtimes"][0]["heartbeat_interval_seconds"] == 10
        assert body["runtimes"][1]["is_stale"] is True
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_admin_prune_runtime_heartbeats_success(client):
    from app.api.deps import require_admin
    from app.main import app

    expected = {
        "pruned_at": datetime.now(timezone.utc),
        "runtime_kind": "worker",
        "stale_only": True,
        "retention_seconds": 0,
        "deleted_count": 3,
    }

    app.dependency_overrides[require_admin] = lambda: _make_user("admin")
    try:
        with patch(
            "app.api.v1.endpoints.admin_runtime.admin_runtime_service.prune_runtime_heartbeats",
            new=AsyncMock(return_value=expected),
        ):
            response = client.post(
                "/api/v1/admin/runtime/heartbeats/prune",
                params={"runtime_kind": "worker", "retention_seconds": 0},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["runtime_kind"] == "worker"
        assert body["deleted_count"] == 3
    finally:
        app.dependency_overrides.pop(require_admin, None)