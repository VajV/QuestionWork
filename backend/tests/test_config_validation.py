import pytest

from app.core.config import DEV_DATABASE_URL, DEV_REDIS_URL, Settings, _validate_settings


def _make_settings(**overrides) -> Settings:
    base = {
        "SECRET_KEY": "batch4-test-secret-that-is-at-least-32-chars-long-ok",
        "APP_ENV": "development",
        "DATABASE_URL": DEV_DATABASE_URL,
        "REDIS_URL": DEV_REDIS_URL,
        "FRONTEND_URL": "http://localhost:3000",
        "JWT_ALGORITHM": "HS256",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_development_allows_local_infra_defaults():
    _validate_settings(_make_settings())


def test_staging_requires_explicit_database_url():
    with pytest.raises(RuntimeError, match="DATABASE_URL must be explicitly set"):
        _validate_settings(_make_settings(APP_ENV="staging"))


def test_staging_requires_explicit_redis_url():
    with pytest.raises(RuntimeError, match="REDIS_URL must be explicitly set"):
        _validate_settings(
            _make_settings(
                APP_ENV="staging",
                DATABASE_URL="postgresql://staging_user:staging_pass@staging-db:5432/questionwork",
            )
        )


def test_staging_accepts_explicit_infra_urls():
    _validate_settings(
        _make_settings(
            APP_ENV="staging",
            DATABASE_URL="postgresql://staging_user:staging_pass@staging-db:5432/questionwork",
            REDIS_URL="redis://staging-redis:6379/0",
        )
    )


def test_totp_required_without_pyotp_fails_fast(monkeypatch):
    """When ADMIN_TOTP_REQUIRED=True but pyotp is not importable, startup must fail."""
    import builtins

    real_import = builtins.__import__

    def _block_pyotp(name, *args, **kwargs):
        if name == "pyotp":
            raise ImportError("mocked: pyotp not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_pyotp)

    with pytest.raises(RuntimeError, match="pyotp.*not installed"):
        _validate_settings(_make_settings(
            ADMIN_TOTP_REQUIRED=True,
            TOTP_ENCRYPTION_KEY="test-totp-enc-key-at-least-32-chars-long",
        ))


def test_totp_required_with_pyotp_passes():
    """When ADMIN_TOTP_REQUIRED=True, pyotp installed, and TOTP_ENCRYPTION_KEY set, no error."""
    _validate_settings(_make_settings(
        ADMIN_TOTP_REQUIRED=True,
        TOTP_ENCRYPTION_KEY="test-totp-enc-key-at-least-32-chars-long",
    ))


def test_totp_required_without_encryption_key_fails():
    """When ADMIN_TOTP_REQUIRED=True but TOTP_ENCRYPTION_KEY is empty, startup must fail."""
    with pytest.raises(RuntimeError, match="TOTP_ENCRYPTION_KEY must be set"):
        _validate_settings(_make_settings(ADMIN_TOTP_REQUIRED=True, TOTP_ENCRYPTION_KEY=""))


def test_stale_running_timeout_must_exceed_worker_heartbeat_interval():
    with pytest.raises(
        RuntimeError,
        match="STALE_RUNNING_TIMEOUT_SECONDS must be greater than WORKER_HEARTBEAT_INTERVAL_SECONDS",
    ):
        _validate_settings(
            _make_settings(
                WORKER_HEARTBEAT_INTERVAL_SECONDS=15,
                STALE_RUNNING_TIMEOUT_SECONDS=15,
            )
        )


def test_arq_runtime_settings_accept_valid_overrides():
    _validate_settings(
        _make_settings(
            ARQ_REDIS_URL="redis://queue-redis:6379/3",
            JOB_DEFAULT_QUEUE_NAME="default",
            JOB_OPS_QUEUE_NAME="ops",
            SCHEDULER_POLL_INTERVAL_SECONDS=10,
            WORKER_HEARTBEAT_INTERVAL_SECONDS=15,
            STALE_RUNNING_TIMEOUT_SECONDS=120,
            ORPHANED_QUEUED_RECOVERY_INTERVAL_SECONDS=30,
        )
    )


def test_arq_redis_url_cannot_be_blank():
    with pytest.raises(RuntimeError, match="ARQ_REDIS_URL must be unset or a non-empty Redis URL"):
        _validate_settings(_make_settings(ARQ_REDIS_URL="   "))


def test_analytics_events_retention_days_must_be_positive():
    with pytest.raises(RuntimeError, match="ANALYTICS_EVENTS_RETENTION_DAYS must be > 0"):
        _validate_settings(_make_settings(ANALYTICS_EVENTS_RETENTION_DAYS=0))