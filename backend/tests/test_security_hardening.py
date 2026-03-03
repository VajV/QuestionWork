"""
Tests for security hardening: admin IP allowlist, TOTP dependency check,
and TOTP setup/enable/disable endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from fastapi import HTTPException


# ──────────────────────────────────────────────────────────────────────
# Helpers shared with test_admin_endpoints
# ──────────────────────────────────────────────────────────────────────

def _make_admin():
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats
    return UserProfile(
        id="admin_test",
        username="test_admin",
        role=UserRoleEnum.admin,
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(),
        badges=[],
        skills=[],
    )


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
        return None

    async def execute(self, *a, **kw):
        return "UPDATE 0"

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


# ──────────────────────────────────────────────────────────────────────
# TestClient fixture
# ──────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────
# IP Allowlist tests
# ──────────────────────────────────────────────────────────────────────

class TestIPAllowlist:
    """Unit tests for the IP allowlist logic inside require_admin."""

    @pytest.mark.asyncio
    async def test_empty_allowlist_permits_all(self):
        """ADMIN_IP_ALLOWLIST='' → any IP is allowed."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()

        request = MagicMock()
        request.client.host = "192.168.99.1"

        conn = _MockConn()

        original = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False

            user = await require_admin(
                request=request,
                current_user=admin_user,
                conn=conn,
                x_totp_token=None,
            )
            assert user.id == "admin_test"
        finally:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original

    @pytest.mark.asyncio
    async def test_allowlist_rejects_unlisted_ip(self):
        """An IP not in the allowlist receives a 403."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "10.0.0.50"

        conn = _MockConn()

        original = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = "10.0.0.1,10.0.0.2"
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token=None,
                )
            assert exc_info.value.status_code == 403
            assert "IP" in exc_info.value.detail
        finally:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original

    @pytest.mark.asyncio
    async def test_allowlist_accepts_cidr(self):
        """CIDR notation e.g. 10.0.0.0/24 should match any IP in subnet."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "10.0.0.123"

        conn = _MockConn()

        original = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = "10.0.0.0/24"
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False

            user = await require_admin(
                request=request,
                current_user=admin_user,
                conn=conn,
                x_totp_token=None,
            )
            assert user.id == "admin_test"
        finally:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original


# ──────────────────────────────────────────────────────────────────────
# TOTP dependency check tests
# ──────────────────────────────────────────────────────────────────────

class TestTotpDependency:
    @pytest.mark.asyncio
    async def test_totp_not_required_skips_check(self):
        """When ADMIN_TOTP_REQUIRED=False the TOTP header is not validated."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        conn = _MockConn()

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            user = await require_admin(
                request=request,
                current_user=admin_user,
                conn=conn,
                x_totp_token=None,
            )
            assert user.id == "admin_test"
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip

    @pytest.mark.asyncio
    async def test_totp_required_but_not_configured_returns_403(self):
        """User without totp_secret but TOTP required → 403."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        conn = _MockConn()
        conn.fetchval = AsyncMock(return_value=None)  # no totp_secret

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token=None,
                )
            assert exc_info.value.status_code == 403
            assert "not configured" in exc_info.value.detail
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip

    @pytest.mark.asyncio
    async def test_totp_required_missing_header(self):
        """totp_secret set but no header → 403."""
        import pyotp
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        secret = pyotp.random_base32()
        conn = _MockConn()
        conn.fetchval = AsyncMock(return_value=secret)

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token=None,  # no token
                )
            assert exc_info.value.status_code == 403
            assert "X-TOTP-Token" in exc_info.value.detail
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip

    @pytest.mark.asyncio
    async def test_totp_required_valid_token_passes(self):
        """Correct TOTP token → user returned."""
        import pyotp
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        secret = pyotp.random_base32()
        valid_token = pyotp.TOTP(secret).now()

        conn = _MockConn()
        conn.fetchval = AsyncMock(return_value=secret)

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            user = await require_admin(
                request=request,
                current_user=admin_user,
                conn=conn,
                x_totp_token=valid_token,
            )
            assert user.id == "admin_test"
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip

    @pytest.mark.asyncio
    async def test_totp_required_wrong_token_403(self):
        """Wrong token → 403."""
        import pyotp
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        secret = pyotp.random_base32()
        conn = _MockConn()
        conn.fetchval = AsyncMock(return_value=secret)

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token="000000",
                )
            assert exc_info.value.status_code == 403
            assert "Invalid" in exc_info.value.detail
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip


# ──────────────────────────────────────────────────────────────────────
# TOTP HTTP endpoint tests
# ──────────────────────────────────────────────────────────────────────

class TestTotpEndpoints:
    def test_setup_returns_secret_and_uri(self, client):
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection

        class _ConnTotp(_MockConn):
            def __init__(self):
                super().__init__()
                self.stored_secret = None

            async def execute(self, *a, **kw):
                return "UPDATE 1"

        async def _ok_conn():
            yield _ConnTotp()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _ok_conn
        try:
            r = client.post("/api/v1/admin/auth/totp/setup")
            assert r.status_code == 200
            body = r.json()
            assert "secret" in body
            assert "otpauth_uri" in body
            assert "otpauth://totp/" in body["otpauth_uri"]
            # Verify the returned secret is a valid base32 TOTP key
            assert len(body["secret"]) >= 16
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_enable_with_valid_token(self, client):
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection

        secret = pyotp.random_base32()
        valid_token = pyotp.TOTP(secret).now()

        class _ConnWithSecret(_MockConn):
            async def fetchval(self, *a, **kw):
                return secret

        async def _ok_conn():
            yield _ConnWithSecret()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _ok_conn
        try:
            r = client.post("/api/v1/admin/auth/totp/enable", json={"token": valid_token})
            assert r.status_code == 200
            assert r.json()["ok"] is True
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_enable_with_wrong_token_returns_400(self, client):
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection

        secret = pyotp.random_base32()

        class _ConnWithSecret(_MockConn):
            async def fetchval(self, *a, **kw):
                return secret

        async def _ok_conn():
            yield _ConnWithSecret()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _ok_conn
        try:
            r = client.post("/api/v1/admin/auth/totp/enable", json={"token": "000000"})
            assert r.status_code == 400
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_enable_without_setup_returns_400(self, client):
        from app.api.deps import require_admin_role_only
        from app.main import app

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        try:
            r = client.post("/api/v1/admin/auth/totp/enable", json={"token": "123456"})
            assert r.status_code == 400
            assert "setup" in r.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)

    def test_disable_clears_secret(self, client):
        from app.api.deps import require_admin_role_only
        from app.main import app

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        try:
            r = client.delete("/api/v1/admin/auth/totp")
            assert r.status_code == 200
            assert r.json()["ok"] is True
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)

    def test_setup_requires_admin_role(self, client):
        """Unauthenticated → 401."""
        r = client.post("/api/v1/admin/auth/totp/setup")
        assert r.status_code == 401
