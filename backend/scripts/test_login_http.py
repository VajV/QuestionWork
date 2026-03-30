import asyncio
import httpx

async def test():
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8001') as client:
        r = await client.post('/api/v1/auth/login', json={'username': 'novice_dev', 'password': 'wrong_password_xyz'})
        print(f'Wrong password Status: {r.status_code}')
        print(f'Wrong password Body: {r.text}')
        r2 = await client.post('/api/v1/auth/login', json={'username': 'novice_dev', 'password': 'password123'})
        print(f'Valid login Status: {r2.status_code}')
        body = r2.json()
        has_token = 'access_token' in body
        print(f'Valid login has access_token: {has_token}')

asyncio.run(test())
