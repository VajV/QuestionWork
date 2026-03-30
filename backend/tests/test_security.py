import pytest

from app.core import security
from app.core.config import settings


@pytest.fixture(autouse=True)
def _reset_refresh_store(monkeypatch):
    security._IN_MEMORY_REFRESH_STORE.clear()
    monkeypatch.setattr(security, "_IN_MEMORY_REFRESH_STORE", security._IN_MEMORY_REFRESH_STORE)
    yield
    security._IN_MEMORY_REFRESH_STORE.clear()


@pytest.mark.asyncio
async def test_refresh_token_lifecycle(monkeypatch):
    # Force in-memory fallback by disabling Redis URL
    monkeypatch.setattr(settings, "REDIS_URL", None)

    user_id = "test_user_1"
    token, expires = await security.create_refresh_token(user_id)

    assert token is not None and isinstance(token, str)
    assert expires > 0

    # Verify token resolves to user_id
    resolved = await security.verify_refresh_token(token)
    assert resolved == user_id

    # Revoke and ensure it no longer verifies
    await security.revoke_refresh_token(token)
    assert await security.verify_refresh_token(token) is None


@pytest.mark.asyncio
async def test_create_refresh_token_uses_memory_store_outside_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "REDIS_URL", None)

    token, expires = await security.create_refresh_token("dev_user")

    assert expires > 0
    assert await security.verify_refresh_token(token) == "dev_user"


@pytest.mark.asyncio
async def test_create_refresh_token_raises_domain_error_when_redis_required_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://example.invalid:6379/0")

    async def _return_none(*, required_in_production=False):
        return None

    monkeypatch.setattr(security, "get_redis_client", _return_none)

    with pytest.raises(RuntimeError) as exc_info:
        await security.create_refresh_token("prod_user")

    assert type(exc_info.value).__name__ == "RefreshTokenStoreUnavailableError"


@pytest.mark.asyncio
async def test_verify_refresh_token_raises_domain_error_when_redis_required_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://example.invalid:6379/0")

    async def _return_none(*, required_in_production=False):
        return None

    monkeypatch.setattr(security, "get_redis_client", _return_none)

    with pytest.raises(RuntimeError) as exc_info:
        await security.verify_refresh_token("refresh-token")

    assert type(exc_info.value).__name__ == "RefreshTokenStoreUnavailableError"


@pytest.mark.asyncio
async def test_revoke_refresh_token_raises_domain_error_when_redis_required_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://example.invalid:6379/0")

    async def _return_none(*, required_in_production=False):
        return None

    monkeypatch.setattr(security, "get_redis_client", _return_none)

    with pytest.raises(RuntimeError) as exc_info:
        await security.revoke_refresh_token("refresh-token")

    assert type(exc_info.value).__name__ == "RefreshTokenStoreUnavailableError"


def test_access_token_contains_issuer_and_audience():
    token = security.create_access_token({"sub": "user_123"})

    payload = security.decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "user_123"
    assert payload["iss"] == "questionwork"
    assert payload["aud"] == "questionwork-api"
    assert "iat" in payload


def test_decode_access_token_rejects_missing_audience():
    import jwt
    from datetime import datetime, timedelta, timezone

    token = jwt.encode(
        {
            "sub": "user_123",
            "iss": "questionwork",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    assert security.decode_access_token(token) is None


def test_decode_access_token_rejects_wrong_issuer():
    import jwt
    from datetime import datetime, timedelta, timezone

    token = jwt.encode(
        {
            "sub": "user_123",
            "iss": "wrong-issuer",
            "aud": "questionwork-api",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    assert security.decode_access_token(token) is None
