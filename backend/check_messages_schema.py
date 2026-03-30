import asyncio
import asyncpg

async def main():
    c = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/questionwork")
    rows = await c.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'quest_message%'"
    )
    print("Tables:", [r["table_name"] for r in rows])

    # Check if rate_limits table exists (needed for check_rate_limit)
    rl = await c.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name = 'rate_limits'"
    )
    print("rate_limits table:", [r["table_name"] for r in rl])

    await c.close()

asyncio.run(main())
