"""Seed a deterministic active event for E2E test coverage."""
import asyncio
import asyncpg


async def seed():
    conn = await asyncpg.connect(
        "postgresql://postgres:postgres@localhost:5432/questionwork"
    )
    try:
        existing = await conn.fetchval(
            "SELECT id FROM events WHERE id = $1", "evt_seed_spring2026"
        )
        if existing:
            print(f"Event already exists: {existing}")
            return

        await conn.execute(
            """
            INSERT INTO events
                (id, title, description, status, xp_multiplier,
                 badge_reward_id, max_participants, created_by,
                 start_at, end_at, created_at, updated_at)
            VALUES
                ($1, $2, $3, 'active', 1.50,
                 NULL, 100, 'admin',
                 NOW(), NOW() + INTERVAL '48 hours',
                 NOW(), NOW())
            """,
            "evt_seed_spring2026",
            "Spring Code Sprint 2026",
            "Complete quests to earn bonus XP during the spring code sprint event!",
        )
        print("Created event: evt_seed_spring2026 (active, 48h)")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
