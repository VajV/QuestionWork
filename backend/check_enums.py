import asyncio, asyncpg

async def main():
    c = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/questionwork")
    for t, col in [("growth_leads", "status"), ("disputes", "status")]:
        r = await c.fetchrow(
            "SELECT data_type, udt_name FROM information_schema.columns WHERE table_name=$1 AND column_name=$2",
            t, col
        )
        if r:
            print(f"{t}.{col}: data_type={r['data_type']}, udt_name={r['udt_name']}")
        else:
            print(f"{t}.{col}: NOT FOUND (table may not exist)")
    await c.close()

asyncio.run(main())
