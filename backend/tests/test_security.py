from app.core import security
from app.core.config import settings


def test_refresh_token_lifecycle(monkeypatch):
    # Force in-memory fallback by disabling Redis URL
    monkeypatch.setattr(settings, "REDIS_URL", None)

    user_id = "test_user_1"
    token, expires = security.create_refresh_token(user_id)

    assert token is not None and isinstance(token, str)
    assert expires > 0

    # Verify token resolves to user_id
    resolved = security.verify_refresh_token(token)
    assert resolved == user_id

    # Revoke and ensure it no longer verifies
    security.revoke_refresh_token(token)
    assert security.verify_refresh_token(token) is None
