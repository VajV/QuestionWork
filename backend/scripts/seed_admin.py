"""
seed_admin.py — Create or update the default admin user.

Reads ADMIN_DEFAULT_PASSWORD from .env (or environment).
If the password is not set, exits with a helpful message.

Usage:
    cd backend
    python scripts/seed_admin.py

The admin user will have:
    id:       admin
    username: admin
    role:     admin
    email:    admin@questionwork.local  (override with ADMIN_EMAIL env var)
"""

import asyncio
import logging
import os
import sys
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BACKEND, ".env"))
except ImportError:
    pass

import asyncpg
from app.core.config import settings
from app.core.security import get_password_hash as hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_admin")

ADMIN_ID = "admin"
ADMIN_USERNAME = "admin"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@questionwork.local")


async def seed() -> None:
    if not settings.ADMIN_DEFAULT_PASSWORD:
        logger.error(
            "ADMIN_DEFAULT_PASSWORD is not set in .env. "
            "Set it before running this script."
        )
        sys.exit(1)

    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id, role FROM users WHERE id = $1 OR username = $2",
                ADMIN_ID,
                ADMIN_USERNAME,
            )

            password_hash = hash_password(settings.ADMIN_DEFAULT_PASSWORD)

            if existing:
                await conn.execute(
                    """
                    UPDATE users
                    SET role = 'admin', password_hash = $1, email = $2
                    WHERE id = $3
                    """,
                    password_hash,
                    ADMIN_EMAIL,
                    existing["id"],
                )
                logger.info(
                    f"Admin user '{ADMIN_USERNAME}' updated "
                    f"(id={existing['id']}, previous role={existing['role']})."
                )
            else:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                await conn.execute(
                    """
                    INSERT INTO users
                        (id, username, email, password_hash, role,
                         level, grade, xp, xp_to_next,
                         stats_int, stats_dex, stats_cha,
                         badges, skills, stat_points,
                         created_at, updated_at)
                    VALUES
                        ($1, $2, $3, $4, 'admin',
                         1, 'novice', 0, 100,
                         10, 10, 10,
                         '[]', '[]', 0,
                         $5, $5)
                    """,
                    ADMIN_ID,
                    ADMIN_USERNAME,
                    ADMIN_EMAIL,
                    password_hash,
                    now,
                )
                logger.info(
                    f"Admin user '{ADMIN_USERNAME}' created "
                    f"(id={ADMIN_ID}, email={ADMIN_EMAIL})."
                )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(seed())
