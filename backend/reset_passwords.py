"""Reset passwords for admin and novice_dev users."""
import asyncio
import asyncpg
import bcrypt

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/questionwork")
    updates = [
        ("admin", "Admin123!"),
        ("novice_dev", "password123"),
    ]
    for username, password in updates:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode("utf-8")
        result = await conn.execute(
            "UPDATE users SET password_hash=$1 WHERE username=$2",
            hashed, username,
        )
        print(f"{username}: {result}")

    # Verify
    for username, password in updates:
        row = await conn.fetchrow("SELECT password_hash FROM users WHERE username=$1", username)
        match = bcrypt.checkpw(password.encode(), row["password_hash"].encode())
        print(f"{username} verify: match={match}")

    await conn.close()

asyncio.run(main())
