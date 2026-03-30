import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/questionwork')
    try:
        rows = await conn.fetch('SELECT DISTINCT type FROM transactions ORDER BY type')
        print("=== Transaction types in DB ===")
        for r in rows:
            print(f"  {r['type']!r}")
        rows2 = await conn.fetch('SELECT DISTINCT status FROM transactions ORDER BY status')
        print("=== Transaction statuses in DB ===")
        for r in rows2:
            print(f"  {r['status']!r}")
        # Check current alembic revision
        rev = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"=== Alembic current revision: {rev} ===")
    finally:
        await conn.close()

asyncio.run(check())
