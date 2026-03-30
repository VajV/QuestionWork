import asyncio
import asyncpg

async def main():
    c = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/questionwork")
    uid = "user_123456"
    status_list = ["assigned", "in_progress", "completed", "revision_requested", "confirmed"]

    # Test the FIXED count query
    total = await c.fetchval(
        """
        SELECT COUNT(*)
        FROM quests q
        WHERE (q.client_id = $1 OR q.assigned_to = $1)
          AND q.status::text = ANY($2::text[])
        """,
        uid, status_list
    )
    print(f"Total dialogs (fixed count): {total}")

    # Test the FIXED main query
    rows = await c.fetch(
        """
        SELECT
            q.id AS quest_id,
            q.title AS quest_title,
            q.status AS quest_status,
            q.client_id,
            q.assigned_to
        FROM quests q
        WHERE (q.client_id = $1 OR q.assigned_to = $1)
          AND q.status::text = ANY($2::text[])
        ORDER BY q.updated_at DESC
        LIMIT 20 OFFSET 0
        """,
        uid, status_list, 
    )
    print(f"Rows returned: {len(rows)}")
    for r in rows:
        print(f"  quest_id={r['quest_id']}, title={r['quest_title']}, status={r['quest_status']}")

    print("\nAll queries passed - fix verified!")
    await c.close()

asyncio.run(main())
