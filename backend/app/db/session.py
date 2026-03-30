"""Настройка подключения к PostgreSQL через asyncpg."""

import asyncio
from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator, Optional

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────
# Raw asyncpg pool (used by existing endpoints)
# ────────────────────────────────────────────
pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()

_POSTGRES_CONNECTION_ERROR = getattr(asyncpg, "PostgresConnectionError", None)
_DB_UNAVAILABLE_ERROR_TYPES = tuple(
    error_type
    for error_type in (
        asyncpg.InterfaceError,
        _POSTGRES_CONNECTION_ERROR,
        ConnectionError,
        OSError,
        TimeoutError,
    )
    if error_type is not None
)


def _asyncpg_url() -> str:
    """Return DATABASE_URL suitable for raw asyncpg (postgresql://)."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def _validate_required_schema(conn: asyncpg.Connection) -> None:
    """Fail fast when required quest schema changes have not been migrated."""
    has_quests_table = await conn.fetchval(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'quests'
        """
    )
    if not has_quests_table:
        raise RuntimeError("Database schema is incomplete: quests table is missing")

    has_fee_column = await conn.fetchval(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'quests'
          AND column_name = 'platform_fee_percent'
        """
    )
    if not has_fee_column:
        raise RuntimeError(
            "Database schema is out of date: quests.platform_fee_percent is missing. "
            "Run Alembic migrations before starting the API."
        )


async def init_db_pool():
    """Инициализация пула соединений с БД"""
    global pool

    db_url = _asyncpg_url()
    try:
        pool = await asyncpg.create_pool(
            db_url,
            min_size=settings.DB_POOL_MIN_SIZE,
            max_size=settings.DB_POOL_MAX_SIZE,
            command_timeout=60,
            timeout=30,  # seconds to wait when pool is exhausted
        )
        async with pool.acquire() as conn:
            await _validate_required_schema(conn)
        logger.info("Подключение к базе данных PostgreSQL успешно установлено")
    except Exception as e:
        if pool is not None:
            await pool.close()
            pool = None
        logger.error(f"Ошибка при подключении к БД: {e}")
        raise


async def close_db_pool():
    """Закрытие пула соединений"""
    global pool
    if pool is not None:
        await pool.close()
        pool = None
        logger.info("Пул соединений с БД закрыт")


def get_db_pool() -> asyncpg.Pool:
    """Return the initialized asyncpg pool for non-HTTP runtimes."""
    if pool is None:
        raise RuntimeError("Пул соединений БД не инициализирован")
    return pool


async def ensure_db_pool() -> asyncpg.Pool:
    """Initialize the pool lazily for worker/scheduler processes."""
    async with _pool_lock:
        if pool is None:
            await init_db_pool()
    return get_db_pool()


@asynccontextmanager
async def acquire_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Shared connection acquisition helper for non-HTTP runtimes."""
    db_pool = await ensure_db_pool()
    async with db_pool.acquire() as connection:
        yield connection


async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Dependency для FastAPI: получение соединения из пула.
    Используется в endpoints через Depends(get_db_connection).
    """
    try:
        async with acquire_db_connection() as connection:
            yield connection
    except Exception as exc:
        if not _is_db_unavailable_error(exc):
            raise

        logger.error("Database temporarily unavailable: %s", exc)
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        ) from exc


def _is_db_unavailable_error(exc: Exception) -> bool:
    current: Exception | None = exc
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        if isinstance(current, _DB_UNAVAILABLE_ERROR_TYPES):
            return True

        visited.add(id(current))
        current = current.__cause__ or current.__context__

    return False
