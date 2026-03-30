"""Debug script: test login endpoint and get traceback."""
import asyncio
import sys
sys.path.insert(0, ".")

async def main():
    import httpx
    
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001") as client:
        # Test 1: login with non-existent user
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent_debug_user", "password": "wrong"},
        )
        print(f"Test 1 (non-existent user): {r.status_code} — {r.text}")

        # Test 2: try to register first, then login with wrong password
        import uuid
        uname = f"debug_{uuid.uuid4().hex[:8]}"
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "username": uname,
                "email": f"{uname}@test.com",
                "password": "DebugPass!99",
                "role": "freelancer",
            },
        )
        print(f"Test 2a (register): {reg.status_code}")
        if reg.status_code in (200, 201):
            r2 = await client.post(
                "/api/v1/auth/login",
                json={"username": uname, "password": "WRONG_PASSWORD"},
            )
            print(f"Test 2b (wrong password for existing user): {r2.status_code} — {r2.text}")


asyncio.run(main())
