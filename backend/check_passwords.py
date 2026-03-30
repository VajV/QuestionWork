"""Quick password verification script."""
import asyncio
import asyncpg
import bcrypt

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/questionwork")
    for user, pwd in [("admin", "Admin123!"), ("novice_dev", "password123")]:
        row = await conn.fetchrow("SELECT password_hash FROM users WHERE username=$1", user)
        if row:
            h = row["password_hash"]
            match = bcrypt.checkpw(pwd.encode(), h.encode())
            print(f"{user}: match={match}  hash_prefix={h[:30]}")
        else:
            print(f"{user}: NOT FOUND")
    await conn.close()

asyncio.run(main())
