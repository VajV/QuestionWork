"""Seed test users for E2E tests."""
import asyncio
import asyncpg
import bcrypt
import uuid


async def seed():
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/questionwork")

    # User 1: test_hero with strong password
    pw_hash1 = bcrypt.hashpw(b"QuestWork1!", bcrypt.gensalt()).decode()
    existing1 = await conn.fetchrow(
        "SELECT id FROM users WHERE email = $1 OR username = $2",
        "test_hero@example.com",
        "test_hero",
    )
    if existing1:
        await conn.execute(
            "UPDATE users SET password_hash = $1, email = $2 WHERE id = $3",
            pw_hash1, "test_hero@example.com", existing1["id"],
        )
        print(f"Updated test_hero: {existing1['id']}")
    else:
        uid1 = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO users (id, username, email, password_hash, role, grade, level, xp, xp_to_next, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())""",
            uid1, "test_hero", "test_hero@example.com", pw_hash1,
            "freelancer", "novice", 1, 0, 100,
        )
        print(f"Created test_hero: {uid1}")

    # User 2: example user (for AI that uses example@gmail.com / password123)
    pw_hash2 = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    existing2 = await conn.fetchrow(
        "SELECT id FROM users WHERE email = $1 OR username = $2",
        "example@gmail.com",
        "example_user",
    )
    if existing2:
        await conn.execute(
            "UPDATE users SET password_hash = $1, email = $2 WHERE id = $3",
            pw_hash2, "example@gmail.com", existing2["id"],
        )
        print(f"Updated example_user: {existing2['id']}")
    else:
        uid2 = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO users (id, username, email, password_hash, role, grade, level, xp, xp_to_next, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())""",
            uid2, "example_user", "example@gmail.com", pw_hash2,
            "client", "novice", 1, 0, 100,
        )
        print(f"Created example_user: {uid2}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
