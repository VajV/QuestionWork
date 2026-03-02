"""
Настройка подключения к PostgreSQL через asyncpg + SQLAlchemy async sessions.
"""

import logging
from typing import AsyncGenerator

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────
# Raw asyncpg pool (used by existing endpoints)
# ────────────────────────────────────────────
pool: asyncpg.Pool = None


def _asyncpg_url() -> str:
    """Return DATABASE_URL suitable for raw asyncpg (postgresql://)."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _sa_url() -> str:
    """Return DATABASE_URL suitable for SQLAlchemy asyncpg driver."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def init_db_pool():
    """Инициализация пула соединений с БД"""
    global pool

    db_url = _asyncpg_url()
    try:
        pool = await asyncpg.create_pool(
            db_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        logger.info("Подключение к базе данных PostgreSQL успешно установлено")
    except Exception as e:
        logger.error(f"Ошибка при подключении к БД: {e}")
        raise


async def close_db_pool():
    """Закрытие пула соединений"""
    global pool
    if pool is not None:
        await pool.close()
        logger.info("Пул соединений с БД закрыт")


async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Dependency для FastAPI: получение соединения из пула.
    Используется в endpoints через Depends(get_db_connection).
    """
    if pool is None:
        raise RuntimeError("Пул соединений БД не инициализирован")

    async with pool.acquire() as connection:
        yield connection


# ────────────────────────────────────────────
# SQLAlchemy async engine & session factory
# ────────────────────────────────────────────
engine = create_async_engine(
    _sa_url(),
    pool_size=5,
    max_overflow=10,
    echo=False,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a SQLAlchemy async session (auto-closes)."""
    async with async_session_factory() as session:
        yield session
