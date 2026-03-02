"""
Настройка подключения к PostgreSQL через asyncpg
"""

import logging
from typing import AsyncGenerator

import asyncpg
from app.core.config import settings

logger = logging.getLogger(__name__)

# Глобальный пул соединений
pool: asyncpg.Pool = None


async def init_db_pool():
    """Инициализация пула соединений с БД"""
    global pool

    db_url = settings.DATABASE_URL
    # Убираем asyncpg префикс если он есть (asyncpg принимает стандартный postgresql://)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

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
