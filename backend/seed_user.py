import asyncio
from app.db.session import get_db_connection
from app.core.security import get_password_hash
import uuid
from datetime import datetime, timezone
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

async def seed():
    async for conn in get_db_connection():
        # register example
        uid = str(uuid.uuid4())
        hashed = get_password_hash("password123")
        try:
            await conn.execute("""
                INSERT INTO auth_users (id, email, username, hashed_password, role, is_active, created_at, updated_at)
                VALUES (\, \, \, \, \, \, \, \)
            """, uid, "example@gmail.com", "example", hashed, "client", True, datetime.now(timezone.utc))
            # insert profile
            await conn.execute("""
                INSERT INTO user_profiles (id, username, role, level, current_xp)
                VALUES (\, \, \, 1, 0)
            """, uid, "example", "client")
            print("seeded example@gmail.com")
        except Exception as e:
            print(e)
            
        return

asyncio.run(seed())
