"""Debug login in-process to capture the real exception."""
import asyncio
import sys
import traceback
sys.path.insert(0, ".")

import os
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/questionwork")
os.environ.setdefault("REDIS_URL", "redis://:changeme@127.0.0.1:6379/0")
os.environ.setdefault("SECRET_KEY", "cclVHwVDqN3i4qxpoWqOJ-uHCx457QU-oUvFa-CVWNU")

async def main():
    # Init DB pool
    from app.db.session import init_db_pool, pool as db_pool_before
    await init_db_pool()
    
    from app.db.session import pool
    
    # Directly test the login logic
    async with pool.acquire() as conn:
        from app.core.security import verify_password
        from app.api.deps import _USER_SAFE_COLUMNS
        
        _USER_AUTH_COLUMNS = f"{_USER_SAFE_COLUMNS}, password_hash"
        
        username = "nonexistent_debug_user"
        _q_login = f"SELECT {_USER_AUTH_COLUMNS} FROM users WHERE username = $1"
        
        print(f"Query: SELECT ... FROM users WHERE username = '{username}'")
        try:
            user_row = await conn.fetchrow(_q_login, username)
            print(f"user_row result: {user_row}")
            if not user_row:
                print("User not found - calling dummy verify_password...")
                try:
                    verify_password("dummy_password", "$2b$12$LJ3m4ys3Lg3lE9Q8pBkSp.ZxOXSCmRCVHaLCQ5FhCjXxVx5m5sZ6C")
                    print("verify_password (dummy) completed normally")
                except Exception as e:
                    print(f"verify_password (dummy) RAISED: {type(e).__name__}: {e}")
                    traceback.print_exc()
        except Exception as e:
            print(f"DB query RAISED: {type(e).__name__}: {e}")
            traceback.print_exc()
        
        # Also test with existing user to check wrong password path
        check_user_q = "SELECT username FROM users ORDER BY created_at LIMIT 1"
        existing_user = await conn.fetchrow(check_user_q)
        if existing_user:
            uname = existing_user["username"]
            print(f"\nTesting existing user: {uname}")
            user_row2 = await conn.fetchrow(_q_login, uname)
            if user_row2:
                pwd_hash = user_row2.get("password_hash")
                print(f"password_hash type: {type(pwd_hash)}, value preview: {str(pwd_hash)[:20] if pwd_hash else 'NULL'}")
                if pwd_hash:
                    try:
                        result = verify_password("wrong_password", pwd_hash)
                        print(f"verify_password wrong pass: {result}")
                    except Exception as e:
                        print(f"verify_password RAISED for wrong pass: {type(e).__name__}: {e}")
                        traceback.print_exc()
                else:
                    print("password_hash is NULL!")

asyncio.run(main())
