"""
Конфигурация приложения
Загружает настройки из переменных окружения
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os
import sys
import logging


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
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/questionwork"
    REDIS_URL: str = "redis://localhost:6379"
    
    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    # Refresh tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Cookie settings for refresh token
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    
    # CORS
    FRONTEND_URL: str = "http://localhost:3000"
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Глобальный экземпляр настроек
settings = Settings()


def _validate_settings(s: Settings) -> None:
    """Basic runtime validation for required environment settings.

    This fails fast on startup if critical secrets or URLs are missing or
    left at insecure defaults.
    """
    logger = logging.getLogger("questionwork.config")

    if not s.SECRET_KEY or s.SECRET_KEY == "change-me-in-production":
        msg = (
            "SECRET_KEY is not set or uses the insecure default. "
            "Set SECRET_KEY in your environment or .env file before starting."
        )
        # In production we must fail fast; in development log a warning.
        if s.APP_ENV.lower() == "production":
            logger.error(msg)
            raise RuntimeError(msg)
        else:
            logger.warning(msg)

    if not s.DATABASE_URL:
        msg = "DATABASE_URL is not set. Set a Postgres DATABASE_URL for the app."
        logger.error(msg)
        raise RuntimeError(msg)

    if not s.FRONTEND_URL:
        logger.warning("FRONTEND_URL is not set; CORS may be misconfigured.")


# validate on import/startup
_validate_settings(settings)
