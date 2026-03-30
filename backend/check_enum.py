import asyncio
import asyncpg

async def main():
    c = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/questionwork")
    # Check the type of quests.status column
    col = await c.fetchrow("""
        SELECT data_type, udt_name FROM information_schema.columns
        WHERE table_name='quests' AND column_name='status'
    """)
    print(f"quests.status type: data_type={col['data_type']}, udt_name={col['udt_name']}")

    # Check enum values
    vals = await c.fetch("SELECT unnest(enum_range(NULL::quest_status_enum)) AS val")
    print(f"Enum values: {[r['val'] for r in vals]}")

    # Test the fix: cast the parameter
    uid = "user_123456"
    statuses = ["assigned", "in_progress", "completed", "revision_requested", "confirmed"]
    total = await c.fetchval(
        "SELECT COUNT(*) FROM quests q WHERE (q.client_id=$1 OR q.assigned_to=$1) AND q.status::text = ANY($2::text[])",
        uid, statuses
    )
    print(f"Total with cast fix: {total}")
    await c.close()

asyncio.run(main())
