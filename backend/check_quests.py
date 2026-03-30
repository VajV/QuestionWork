import asyncio, asyncpg

async def main():
    c = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/questionwork")
    rows = await c.fetch(
        "SELECT id, title, status, client_id FROM quests WHERE status = 'open' ORDER BY created_at DESC LIMIT 10"
    )
    print(f"Open quests: {len(rows)}")
    for r in rows:
        print(f"  {r['id'][:12]}... title={r['title'][:40]} client={r['client_id']}")

    total = await c.fetchval("SELECT COUNT(*) FROM quests")
    by_status = await c.fetch(
        "SELECT status::text, COUNT(*) as cnt FROM quests GROUP BY status ORDER BY cnt DESC"
    )
    print(f"\nTotal quests: {total}")
    for r in by_status:
        print(f"  {r['status']}: {r['cnt']}")
    await c.close()

asyncio.run(main())
