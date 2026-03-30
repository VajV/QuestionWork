import httpx

r = httpx.post("http://127.0.0.1:8001/api/v1/auth/login", json={"username": "test_hero", "password": "QuestWork1!"}, timeout=5)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"User: {data.get('user', {}).get('username')}")
    print(f"Token prefix: {data.get('access_token', '')[:20]}")
else:
    print(f"Error: {r.text[:300]}")

# Also test email-based login
r2 = httpx.post("http://127.0.0.1:8001/api/v1/auth/login", json={"username": "test_hero@example.com", "password": "QuestWork1!"}, timeout=5)
print(f"\nEmail login status: {r2.status_code}")
if r2.status_code == 200:
    print("Email login: OK")
else:
    print(f"Email login error: {r2.text[:300]}")
