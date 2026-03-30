"""Flush login-related rate-limit keys from Redis."""
import asyncio
import redis.asyncio as aioredis


async def main():
    r = aioredis.from_url("redis://:changeme@localhost:6379/0")
    keys = await r.keys("ratelimit:*")
    for k in keys:
        await r.delete(k)
    print(f"Deleted {len(keys)} rate-limit keys")
    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
