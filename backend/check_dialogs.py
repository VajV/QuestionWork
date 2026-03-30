import asyncio
import asyncpg

async def main():
    c = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/questionwork")

    # Check if novice_dev has any quests in allowed statuses
    user = await c.fetchrow("SELECT id FROM users WHERE username='novice_dev'")
    if not user:
        print("ERROR: novice_dev not found")
        await c.close()
        return

    uid = user["id"]
    print(f"novice_dev id: {uid}")

    statuses = ["assigned", "in_progress", "completed", "revision_requested", "confirmed"]
    quests = await c.fetch(
        "SELECT id, title, status, client_id, assigned_to FROM quests WHERE (client_id=$1 OR assigned_to=$1) AND status=ANY($2::text[])",
        uid, statuses
    )
    print(f"Quests with allowed statuses: {len(quests)}")
    for q in quests:
        print(f"  {q['id']} | {q['title']} | status={q['status']} | client={q['client_id']} | assigned={q['assigned_to']}")

    # Try the exact query from list_dialogs
    try:
        total = await c.fetchval(
            """SELECT COUNT(*) FROM quests q
               WHERE (q.client_id=$1 OR q.assigned_to=$1) AND q.status=ANY($2::text[])""",
            uid, statuses
        )
        print(f"Total matching quests: {total}")
    except Exception as e:
        print(f"Count query error: {e}")

    # Try the full dialogs query
    try:
        rows = await c.fetch(
            """
            SELECT
                q.id AS quest_id,
                q.title AS quest_title,
                q.status AS quest_status,
                q.client_id,
                q.assigned_to,
                client.username AS client_username,
                freelancer.username AS freelancer_username,
                last_msg.text AS last_message_text,
                last_msg.message_type AS last_message_type,
                last_msg.created_at AS last_message_at,
                COALESCE(unread.cnt, 0) AS unread_count
            FROM quests q
            JOIN users client ON client.id = q.client_id
            LEFT JOIN users freelancer ON freelancer.id = q.assigned_to
            LEFT JOIN LATERAL (
                SELECT qm.text, qm.message_type, qm.created_at
                FROM quest_messages qm
                WHERE qm.quest_id = q.id
                ORDER BY qm.created_at DESC
                LIMIT 1
            ) last_msg ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS cnt
                FROM quest_messages qm
                LEFT JOIN quest_message_reads r
                       ON r.quest_id = q.id AND r.user_id = $1
                WHERE qm.quest_id = q.id
                  AND qm.created_at > COALESCE(r.last_read_at, TIMESTAMP 'epoch')
                  AND COALESCE(qm.author_id, '') <> $1
            ) unread ON TRUE
            WHERE (q.client_id = $1 OR q.assigned_to = $1)
              AND q.status = ANY($2::text[])
            ORDER BY COALESCE(last_msg.created_at, q.updated_at) DESC
            LIMIT $3 OFFSET $4
            """,
            uid, statuses, 50, 0,
        )
        print(f"Dialog rows returned: {len(rows)}")
    except Exception as e:
        print(f"Dialog query FAILED: {type(e).__name__}: {e}")

    await c.close()

asyncio.run(main())
