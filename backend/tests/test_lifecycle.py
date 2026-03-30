"""
Tests for lifecycle service and API endpoint.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient


# ──────────────────────────────────────────────────────
# Mock DB connection
# ──────────────────────────────────────────────────────


class _MockConn:
    def __init__(self):
        self._executed: list[tuple] = []
        self._fetch_result: list = []
        self._fetchrow_result = None
        self._in_transaction = False

    def is_in_transaction(self) -> bool:
        return self._in_transaction

    async def execute(self, query, *args, **kwargs):
        self._executed.append((query, args))
        return "INSERT 0 1"

    async def fetch(self, query, *args, **kwargs):
        return self._fetch_result

    async def fetchrow(self, *a, **kw):
        return self._fetchrow_result

    async def fetchval(self, *a, **kw):
        return None

    def transaction(self):
        conn = self

        class _Tx:
            async def __aenter__(self_):
                conn._in_transaction = True
                return self_

            async def __aexit__(self_, *args):
                conn._in_transaction = False
                return False

        return _Tx()


async def _mock_conn_dep():
    yield _MockConn()


# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────


def _make_admin():
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats

    return UserProfile(
        id="admin_lifecycle_test",
        username="admin_lifecycle",
        role=UserRoleEnum("admin"),
        level=10,
        grade=GradeEnum.senior,
        xp=9999,
        xp_to_next=0,
        stats=UserStats(),
        badges=[],
        skills=[],
    )


# ──────────────────────────────────────────────────────
# lifecycle_service unit tests
# ──────────────────────────────────────────────────────


class TestLifecycleServiceEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_inserts_when_in_transaction(self):
        from app.services.lifecycle_service import enqueue

        conn = _MockConn()
        conn._in_transaction = True

        inserted = await enqueue(
            conn,
            user_id="user_001",
            campaign_key="incomplete_profile",
            idempotency_key="incomplete_profile:user_001:v1",
        )

        assert inserted is True
        assert len(conn._executed) == 1
        query, args = conn._executed[0]
        assert "INSERT INTO lifecycle_messages" in query
        assert args[0] == "user_001"
        assert args[1] == "incomplete_profile"

    @pytest.mark.asyncio
    async def test_enqueue_raises_outside_transaction(self):
        from app.services.lifecycle_service import enqueue

        conn = _MockConn()
        conn._in_transaction = False

        with pytest.raises(RuntimeError, match="transaction"):
            await enqueue(
                conn,
                user_id="user_001",
                campaign_key="incomplete_profile",
                idempotency_key="incomplete_profile:user_001:v1",
            )

    @pytest.mark.asyncio
    async def test_enqueue_returns_false_on_conflict(self):
        from app.services.lifecycle_service import enqueue

        conn = _MockConn()
        conn._in_transaction = True

        # Simulate ON CONFLICT DO NOTHING (returns "INSERT 0 0")
        async def _execute_conflict(query, *args, **kwargs):
            conn._executed.append((query, args))
            return "INSERT 0 0"

        conn.execute = _execute_conflict

        inserted = await enqueue(
            conn,
            user_id="user_001",
            campaign_key="incomplete_profile",
            idempotency_key="incomplete_profile:user_001:v1",
        )

        assert inserted is False

    @pytest.mark.asyncio
    async def test_enqueue_incomplete_profile_sets_delay(self):
        from app.services.lifecycle_service import enqueue_incomplete_profile

        conn = _MockConn()
        conn._in_transaction = True
        before = datetime.now(timezone.utc)

        inserted = await enqueue_incomplete_profile(conn, user_id="user_002")

        assert inserted is True
        query, args = conn._executed[0]
        send_after: datetime = args[3]
        assert send_after > before  # scheduled in the future

    @pytest.mark.asyncio
    async def test_enqueue_dormant_client_encodes_days(self):
        from app.services.lifecycle_service import enqueue_dormant_client

        conn = _MockConn()
        conn._in_transaction = True

        inserted = await enqueue_dormant_client(
            conn, user_id="user_003", days=14, last_quest_id="quest_xyz"
        )

        assert inserted is True
        query, args = conn._executed[0]
        # trigger_data is serialised to JSON string in arg[2]
        td = json.loads(args[2])
        assert td["days_dormant"] == 14
        assert td["last_quest_id"] == "quest_xyz"


class TestLifecycleServiceHelpers:
    @pytest.mark.asyncio
    async def test_mark_sent_updates_status(self):
        from app.services.lifecycle_service import mark_sent

        conn = _MockConn()
        await mark_sent(conn, "msg_001")

        assert len(conn._executed) == 1
        query, args = conn._executed[0]
        assert "status = 'sent'" in query
        assert args[0] == "msg_001"

    @pytest.mark.asyncio
    async def test_mark_failed_stores_error(self):
        from app.services.lifecycle_service import mark_failed

        conn = _MockConn()
        await mark_failed(conn, "msg_002", "SMTP timeout")

        assert len(conn._executed) == 1
        query, args = conn._executed[0]
        assert "status = 'failed'" in query
        assert args[0] == "msg_002"
        assert "SMTP timeout" in args[1]

    @pytest.mark.asyncio
    async def test_suppress_updates_to_suppressed(self):
        from app.services.lifecycle_service import suppress

        conn = _MockConn()
        await suppress(conn, "msg_003")

        assert len(conn._executed) == 1
        assert "suppressed" in conn._executed[0][0]


# ──────────────────────────────────────────────────────
# email_service unit tests (new functions)
# ──────────────────────────────────────────────────────


class TestEmailServiceNewFunctions:
    def test_send_quest_completed_delegates_to_send_quest_confirmed(self):
        from app.services import email_service

        calls = []

        def _mock_confirmed(to, username, quest_title, xp_awarded):
            calls.append({"to": to, "username": username, "quest_title": quest_title, "xp_awarded": xp_awarded})

        with patch.object(email_service, "send_quest_confirmed", _mock_confirmed):
            email_service.send_quest_completed(
                to="user@example.com",
                username="alice",
                quest_title="Build API",
                xp_gained=80,
            )

        assert len(calls) == 1
        assert calls[0]["to"] == "user@example.com"
        assert calls[0]["xp_awarded"] == 80

    def test_send_lifecycle_nudge_skips_when_disabled(self):
        from app.services import email_service

        sent = []

        with patch.object(email_service, "_enabled", return_value=False):
            with patch.object(email_service, "_send", lambda _: sent.append(True)):
                email_service.send_lifecycle_nudge(
                    to="user@example.com",
                    username="alice",
                    subject="Test",
                    body_html="<p>Test</p>",
                )

        assert len(sent) == 0  # _send never called when disabled

    def test_send_lifecycle_nudge_calls_send_when_enabled(self):
        from app.services import email_service
        from unittest.mock import MagicMock

        sent = []

        with patch.object(email_service, "_enabled", return_value=True):
            with patch.object(email_service, "_build_message", return_value=MagicMock()):
                with patch.object(email_service, "_send", lambda _: sent.append(True)):
                    email_service.send_lifecycle_nudge(
                        to="user@example.com",
                        username="alice",
                        subject="Hello",
                        body_html="<p>Hello World</p>",
                    )

        assert len(sent) == 1


# ──────────────────────────────────────────────────────
# HTTP endpoint tests
# ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def lifecycle_client():
    from app.db.session import get_db_connection
    from app.api.deps import require_admin
    from app.main import app

    admin_user = _make_admin()

    app.dependency_overrides[get_db_connection] = _mock_conn_dep
    app.dependency_overrides[require_admin] = lambda: admin_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestLifecycleEndpoint:
    def test_scan_returns_zero_counts(self, lifecycle_client):
        with patch("app.services.lifecycle_service.scan_and_enqueue_dormant_clients", new=AsyncMock(return_value=0)):
            with patch("app.services.lifecycle_service.scan_and_enqueue_stale_shortlists", new=AsyncMock(return_value=0)):
                response = lifecycle_client.post("/api/v1/lifecycle/scan")

        assert response.status_code == 200
        data = response.json()
        assert data["dormant_clients_enqueued"] == 0
        assert data["stale_shortlists_enqueued"] == 0

    def test_scan_returns_nonzero_counts(self, lifecycle_client):
        with patch("app.services.lifecycle_service.scan_and_enqueue_dormant_clients", new=AsyncMock(return_value=5)):
            with patch("app.services.lifecycle_service.scan_and_enqueue_stale_shortlists", new=AsyncMock(return_value=3)):
                response = lifecycle_client.post("/api/v1/lifecycle/scan")

        assert response.status_code == 200
        data = response.json()
        assert data["dormant_clients_enqueued"] == 5
        assert data["stale_shortlists_enqueued"] == 3

    def test_manual_enqueue_incomplete_profile(self, lifecycle_client):
        with patch("app.services.lifecycle_service.enqueue_incomplete_profile", new=AsyncMock(return_value=True)):
            response = lifecycle_client.post(
                "/api/v1/lifecycle/enqueue",
                json={"campaign_key": "incomplete_profile", "user_id": "user_xyz"},
            )

        assert response.status_code == 200
        assert response.json()["inserted"] is True

    def test_manual_enqueue_unknown_campaign_key(self, lifecycle_client):
        response = lifecycle_client.post(
            "/api/v1/lifecycle/enqueue",
            json={"campaign_key": "nonexistent_campaign", "user_id": "user_xyz"},
        )

        assert response.status_code == 400
        assert "Unknown campaign_key" in response.json()["detail"]

    def test_manual_enqueue_quest_draft_requires_quest_id(self, lifecycle_client):
        response = lifecycle_client.post(
            "/api/v1/lifecycle/enqueue",
            json={"campaign_key": "incomplete_quest_draft", "user_id": "user_xyz"},
        )

        assert response.status_code == 400
        assert "quest_id" in response.json()["detail"]

    def test_manual_enqueue_dormant_client(self, lifecycle_client):
        with patch("app.services.lifecycle_service.enqueue_dormant_client", new=AsyncMock(return_value=True)):
            response = lifecycle_client.post(
                "/api/v1/lifecycle/enqueue",
                json={"campaign_key": "dormant_client", "user_id": "user_xyz", "quest_id": "quest_abc"},
            )

        assert response.status_code == 200
        assert response.json()["inserted"] is True

    def test_manual_enqueue_returns_false_for_duplicate(self, lifecycle_client):
        with patch("app.services.lifecycle_service.enqueue_incomplete_profile", new=AsyncMock(return_value=False)):
            response = lifecycle_client.post(
                "/api/v1/lifecycle/enqueue",
                json={"campaign_key": "incomplete_profile", "user_id": "user_already_queued"},
            )

        assert response.status_code == 200
        assert response.json()["inserted"] is False


# ──────────────────────────────────────────────────────
# Task 6: Reactivation cadence — script scan integration
# ──────────────────────────────────────────────────────


class TestProcessLifecycleScriptScan:
    """Verify the scan phase in process_lifecycle_messages.main() runs correctly."""

    @pytest.mark.asyncio
    async def test_main_calls_scan_before_processing(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        import scripts.process_lifecycle_messages as script

        scan_dormant = AsyncMock(return_value=3)
        scan_stale = AsyncMock(return_value=1)
        mock_conn = AsyncMock()

        async def _fake_connect(dsn):
            return mock_conn

        with (
            patch.object(script.lifecycle_service, "scan_and_enqueue_dormant_clients", scan_dormant),
            patch.object(script.lifecycle_service, "scan_and_enqueue_stale_shortlists", scan_stale),
            patch.object(script.lifecycle_service, "get_pending_messages", new=AsyncMock(return_value=[])),
            patch("asyncpg.connect", new=AsyncMock(side_effect=_fake_connect)),
        ):
            await script.main(dry_run=False, limit=10, no_scan=False)

        scan_dormant.assert_called_once()
        scan_stale.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_skips_scan_when_no_scan_flag(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        import scripts.process_lifecycle_messages as script

        scan_dormant = AsyncMock(return_value=0)
        mock_conn = AsyncMock()

        async def _fake_connect(dsn):
            return mock_conn

        with (
            patch.object(script.lifecycle_service, "scan_and_enqueue_dormant_clients", scan_dormant),
            patch.object(script.lifecycle_service, "get_pending_messages", new=AsyncMock(return_value=[])),
            patch("asyncpg.connect", new=AsyncMock(side_effect=_fake_connect)),
        ):
            await script.main(dry_run=False, limit=10, no_scan=True)

        scan_dormant.assert_not_called()

    @pytest.mark.asyncio
    async def test_main_dry_run_skips_scan_calls(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        import scripts.process_lifecycle_messages as script

        scan_dormant = AsyncMock(return_value=0)
        mock_conn = AsyncMock()

        async def _fake_connect(dsn):
            return mock_conn

        with (
            patch.object(script.lifecycle_service, "scan_and_enqueue_dormant_clients", scan_dormant),
            patch.object(script.lifecycle_service, "get_pending_messages", new=AsyncMock(return_value=[])),
            patch("asyncpg.connect", new=AsyncMock(side_effect=_fake_connect)),
        ):
            await script.main(dry_run=True, limit=10, no_scan=False)

        # dry_run=True means scan is skipped (only logged)
        scan_dormant.assert_not_called()
