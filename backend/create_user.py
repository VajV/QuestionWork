import asyncio
from app.api.v1.endpoints.auth import register_public
from app.schemas.user import UserCreate
from app.db.session import get_db_connection
from asgi_lifespan import LifespanManager
from app.main import app

async def main():
    try:
        # We need a db connection
        pool = app.state.pool
        async with pool.acquire() as conn:
            req = UserCreate(email='example@gmail.com', username='example_user', password='password123')
            await register_public(req, None, conn)
            print("User created")
    except Exception as e:
        print("Error:", e)

async def run():
    async with LifespanManager(app):
        await main()

if __name__ == "__main__":
    asyncio.run(run())
