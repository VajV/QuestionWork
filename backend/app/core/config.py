"""
Конфигурация приложения
Загружает настройки из переменных окружения
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os
import sys
import logging
import ipaddress


DEV_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/questionwork"
DEV_REDIS_URL = "redis://localhost:6379"


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Application
    APP_NAME: str = "QuestionWork"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    
    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = DEV_DATABASE_URL
    DB_POOL_MIN_SIZE: int = 5
    DB_POOL_MAX_SIZE: int = 30
    REDIS_URL: str = DEV_REDIS_URL
    ARQ_REDIS_URL: Optional[str] = None

    # Background runtime / queue settings
    JOB_DEFAULT_QUEUE_NAME: str = "default"
    JOB_OPS_QUEUE_NAME: str = "ops"
    SCHEDULER_POLL_INTERVAL_SECONDS: int = 10
    WORKER_HEARTBEAT_INTERVAL_SECONDS: int = 15
    STALE_RUNNING_TIMEOUT_SECONDS: int = 120
    ORPHANED_QUEUED_RECOVERY_INTERVAL_SECONDS: int = 30
    RUNTIME_HEARTBEAT_RETENTION_SECONDS: int = 86400
    
    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 5
    # Refresh tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Cookie settings for refresh token
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"
    
    # CORS
    FRONTEND_URL: str = "http://localhost:3000"
    # Reverse proxies trusted to supply X-Forwarded-For. Empty = ignore XFF entirely.
    TRUSTED_PROXY_CIDRS: str = ""

    # Economy (string defaults → parsed as Decimal at point of use)
    PLATFORM_FEE_PERCENT: str = "10.0"           # % taken by platform on quest payout
    MIN_WITHDRAWAL_AMOUNT: str = "10.0"           # minimum withdrawal per request
    PLATFORM_USER_ID: str = "platform"            # virtual wallet owner for collected fees
    WITHDRAWAL_AUTO_APPROVE_LIMIT: str = "50.0"   # amounts <= this are auto-approved by the processor script
    WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED: bool = False
    WITHDRAWAL_AUTO_APPROVE_BATCH_LIMIT: int = 100

    # RPG balance
    RPG_XP_PER_BUDGET_RATIO: float = 0.1
    RPG_MAX_XP_REWARD: int = 500
    RPG_MIN_XP_REWARD: int = 10
    RPG_COMPLEXITY_BONUS_MULTIPLIER: float = 1.5
    RPG_GRADE_XP_THRESHOLDS: str = "500,2000,5000"
    RPG_CLASS_LEVEL_THRESHOLDS: str = "0,500,1500,3000,6000,10000,16000,24000,35000,50000"

    # Operations / Admin
    NOTIFICATION_RETENTION_DAYS: int = 30        # prune read notifications older than N days
    ADMIN_DEFAULT_PASSWORD: Optional[str] = None # if set, seeds a default admin user on migration

    # Admin security hardening
    # Comma-separated list of allowed IPv4/IPv6 addresses for admin endpoints.
    # Empty string = allow all (development default). In production set to your ops IPs.
    ADMIN_IP_ALLOWLIST: str = ""
    # When True every admin HTTP request must include a valid X-TOTP-Token header.
    ADMIN_TOTP_REQUIRED: bool = False
    # Separate encryption key for TOTP secrets. When empty, falls back to domain-separated SECRET_KEY derivation.
    TOTP_ENCRYPTION_KEY: str = ""

    # Alerting
    # Slack incoming-webhook URL. When set, the cron scripts post summaries/errors.
    SLACK_WEBHOOK_URL: Optional[str] = None

    # Backup
    BACKUP_DIR: str = "/var/backups/questionwork"  # override in .env
    BACKUP_RETENTION_DAYS: int = 7

    # OpenRouter API
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "qwen/qwen-2.5-coder-32b-instruct"
    # Sentry (error reporting)
    SENTRY_DSN: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    OTEL_SERVICE_NAME: str = "questionwork-backend"
    OTEL_SAMPLE_RATE: float = 0.0

    @staticmethod
    def _parse_int_list(raw_value: str, setting_name: str) -> tuple[int, ...]:
        try:
            values = tuple(int(part.strip()) for part in raw_value.split(",") if part.strip())
        except ValueError as exc:
            raise RuntimeError(f"{setting_name} must be a comma-separated list of integers") from exc
        if not values:
            raise RuntimeError(f"{setting_name} must not be empty")
        return values

    @property
    def rpg_grade_xp_thresholds(self) -> tuple[int, int, int]:
        values = self._parse_int_list(self.RPG_GRADE_XP_THRESHOLDS, "RPG_GRADE_XP_THRESHOLDS")
        if len(values) != 3:
            raise RuntimeError("RPG_GRADE_XP_THRESHOLDS must contain exactly 3 thresholds")
        if tuple(sorted(values)) != values:
            raise RuntimeError("RPG_GRADE_XP_THRESHOLDS must be sorted in ascending order")
        return values

    @property
    def rpg_class_level_thresholds(self) -> tuple[int, ...]:
        values = self._parse_int_list(self.RPG_CLASS_LEVEL_THRESHOLDS, "RPG_CLASS_LEVEL_THRESHOLDS")
        if len(values) < 2:
            raise RuntimeError("RPG_CLASS_LEVEL_THRESHOLDS must contain at least 2 thresholds")
        if values[0] != 0:
            raise RuntimeError("RPG_CLASS_LEVEL_THRESHOLDS must start with 0")
        if tuple(sorted(values)) != values:
            raise RuntimeError("RPG_CLASS_LEVEL_THRESHOLDS must be sorted in ascending order")
        return values

    model_config = {"env_file": ".env", "case_sensitive": True}


# Глобальный экземпляр настроек
settings = Settings()


def _validate_settings(s: Settings) -> None:
    """Basic runtime validation for required environment settings.

    This fails fast on startup if critical secrets or URLs are missing or
    left at insecure defaults.
    """
    logger = logging.getLogger("questionwork.config")

    _PLACEHOLDER_KEYS = {
        "changeme", "change-me", "secret", "your-secret-key",
        "your-secret-key-here", "your-secret-key-change-in-production",
        "change-me-in-production", "test", "dev", "development",
    }
    _MIN_SECRET_KEY_LENGTH = 32

    key = (s.SECRET_KEY or "").strip()
    if (
        not key
        or key.lower() in _PLACEHOLDER_KEYS
        or len(key) < _MIN_SECRET_KEY_LENGTH
        or len(set(key)) < 8
    ):
        msg = (
            "SECRET_KEY is not set, uses an insecure placeholder, or is too short. "
            f"Must be at least {_MIN_SECRET_KEY_LENGTH} characters with sufficient entropy. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
        logger.error(msg)
        raise RuntimeError(msg)

    if not s.DATABASE_URL:
        msg = "DATABASE_URL is not set. Set a Postgres DATABASE_URL for the app."
        logger.error(msg)
        raise RuntimeError(msg)

    if not s.REDIS_URL:
        msg = "REDIS_URL is not set. Set a Redis REDIS_URL for the app."
        logger.error(msg)
        raise RuntimeError(msg)

    _ALLOWED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}
    if s.JWT_ALGORITHM not in _ALLOWED_JWT_ALGORITHMS:
        msg = (
            f"JWT_ALGORITHM={s.JWT_ALGORITHM!r} is not allowed. "
            f"Must be one of {sorted(_ALLOWED_JWT_ALGORITHMS)}."
        )
        logger.error(msg)
        raise RuntimeError(msg)

    if not s.FRONTEND_URL:
        logger.warning("FRONTEND_URL is not set; CORS may be misconfigured.")

    trusted_proxy_raw = (s.TRUSTED_PROXY_CIDRS or "").strip()
    if trusted_proxy_raw:
        for entry in [part.strip() for part in trusted_proxy_raw.split(",") if part.strip()]:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError:
                try:
                    ipaddress.ip_address(entry)
                except ValueError as exc:
                    raise RuntimeError(
                        f"TRUSTED_PROXY_CIDRS contains invalid IP/CIDR entry: {entry!r}"
                    ) from exc

    if s.RPG_MIN_XP_REWARD < 0:
        raise RuntimeError("RPG_MIN_XP_REWARD must be >= 0")
    if s.RPG_MAX_XP_REWARD < s.RPG_MIN_XP_REWARD:
        raise RuntimeError("RPG_MAX_XP_REWARD must be >= RPG_MIN_XP_REWARD")
    if s.RPG_XP_PER_BUDGET_RATIO <= 0:
        raise RuntimeError("RPG_XP_PER_BUDGET_RATIO must be > 0")
    if s.RPG_COMPLEXITY_BONUS_MULTIPLIER < 1.0:
        raise RuntimeError("RPG_COMPLEXITY_BONUS_MULTIPLIER must be >= 1.0")

    if s.DB_POOL_MIN_SIZE > s.DB_POOL_MAX_SIZE:
        raise RuntimeError(
            f"DB_POOL_MIN_SIZE ({s.DB_POOL_MIN_SIZE}) must be <= DB_POOL_MAX_SIZE ({s.DB_POOL_MAX_SIZE})"
        )

    if s.SCHEDULER_POLL_INTERVAL_SECONDS <= 0:
        raise RuntimeError("SCHEDULER_POLL_INTERVAL_SECONDS must be > 0")
    if s.WORKER_HEARTBEAT_INTERVAL_SECONDS <= 0:
        raise RuntimeError("WORKER_HEARTBEAT_INTERVAL_SECONDS must be > 0")
    if s.STALE_RUNNING_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("STALE_RUNNING_TIMEOUT_SECONDS must be > 0")
    if s.ORPHANED_QUEUED_RECOVERY_INTERVAL_SECONDS <= 0:
        raise RuntimeError("ORPHANED_QUEUED_RECOVERY_INTERVAL_SECONDS must be > 0")
    if s.RUNTIME_HEARTBEAT_RETENTION_SECONDS <= 0:
        raise RuntimeError("RUNTIME_HEARTBEAT_RETENTION_SECONDS must be > 0")
    if s.STALE_RUNNING_TIMEOUT_SECONDS <= s.WORKER_HEARTBEAT_INTERVAL_SECONDS:
        raise RuntimeError(
            "STALE_RUNNING_TIMEOUT_SECONDS must be greater than WORKER_HEARTBEAT_INTERVAL_SECONDS"
        )

    if s.ARQ_REDIS_URL is not None and not s.ARQ_REDIS_URL.strip():
        raise RuntimeError("ARQ_REDIS_URL must be unset or a non-empty Redis URL")

    _env = s.APP_ENV.lower()
    if _env not in ("development", "dev"):
        if s.DATABASE_URL == DEV_DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL must be explicitly set for non-development environments. "
                "The built-in localhost default is allowed only in development."
            )
        if s.REDIS_URL == DEV_REDIS_URL:
            raise RuntimeError(
                "REDIS_URL must be explicitly set for non-development environments. "
                "The built-in localhost default is allowed only in development."
            )

    # Production-only validations
    if _env in ('production', 'prod'):
        if not s.COOKIE_SECURE:
            raise RuntimeError(
                "COOKIE_SECURE must be True in production. "
                "Set COOKIE_SECURE=True in your environment."
            )
        if not (s.ADMIN_IP_ALLOWLIST or "").strip():
            raise RuntimeError(
                "ADMIN_IP_ALLOWLIST must not be empty in production. "
                "Set allowed admin IPs (e.g. '10.0.0.0/8')."
            )
        if not s.ADMIN_TOTP_REQUIRED:
            raise RuntimeError(
                "ADMIN_TOTP_REQUIRED must be True in production. "
                "Set ADMIN_TOTP_REQUIRED=True in your environment."
            )

    # Fail-fast: verify pyotp is importable when TOTP is required
    if s.ADMIN_TOTP_REQUIRED:
        try:
            import pyotp  # noqa: F811
        except ImportError:
            raise RuntimeError(
                "ADMIN_TOTP_REQUIRED is True but 'pyotp' package is not installed. "
                "Install it with: pip install pyotp"
            )

    # Economy validations
    try:
        fee = float(s.PLATFORM_FEE_PERCENT)
        if fee < 0 or fee > 50:
            raise RuntimeError(
                f"PLATFORM_FEE_PERCENT={s.PLATFORM_FEE_PERCENT} is out of range. Must be 0..50."
            )
    except ValueError:
        raise RuntimeError(
            f"PLATFORM_FEE_PERCENT={s.PLATFORM_FEE_PERCENT!r} is not a valid number."
        )

    _ = s.rpg_grade_xp_thresholds
    _ = s.rpg_class_level_thresholds


# validate on import/startup
_validate_settings(settings)
