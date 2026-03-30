import asyncio
import os
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.db import session
from app.services import guild_card_service


async def main() -> None:
    await session.init_db_pool()
    try:
        if session.pool is None:
            raise RuntimeError("Database pool was not initialized")

        async with session.pool.acquire() as conn:
            guild_rows = await conn.fetch("SELECT id FROM guilds ORDER BY created_at ASC")
            for row in guild_rows:
                async with conn.transaction():
                    inserted = await guild_card_service.backfill_guild_seasonal_rewards(
                        conn,
                        guild_id=str(row["id"]),
                    )
                    print(f"guild={row['id']} inserted={len(inserted)}")
    finally:
        await session.close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())