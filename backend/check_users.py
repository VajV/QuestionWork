import asyncio, asyncpg

async def main():
    c = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/questionwork")
    rows = await c.fetch(
        "SELECT id, username, email, role FROM users WHERE username ILIKE $1 OR email ILIKE $1",
        "%test%"
    )
    for r in rows:
        print(dict(r))
    if not rows:
        print("NO test users found")
    
    # also show all users
    all_users = await c.fetch("SELECT id, username, email, role FROM users ORDER BY created_at")
    print(f"\nAll users ({len(all_users)}):")
    for u in all_users:
        print(f"  {u['username']} ({u['role']}) - {u['email']}")
    await c.close()

asyncio.run(main())
