import asyncio, asyncpg

async def main():
    c = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/questionwork")
    rows = await c.fetch("SELECT column_name FROM information_schema.columns WHERE table_name='users' ORDER BY ordinal_position")
    for r in rows:
        print(r["column_name"])
    await c.close()

asyncio.run(main())
