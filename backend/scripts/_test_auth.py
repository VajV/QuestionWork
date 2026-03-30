import httpx

BASE = "http://127.0.0.1:8001"

# Test username login
r = httpx.post(f"{BASE}/api/v1/auth/login", json={"username": "test_hero", "password": "QuestWork1!"}, timeout=5)
print(f"Username login: {r.status_code}")

# Test email login
r2 = httpx.post(f"{BASE}/api/v1/auth/login", json={"username": "test_hero@example.com", "password": "QuestWork1!"}, timeout=5)
print(f"Email login: {r2.status_code}")
if r2.status_code != 200:
    print(f"  Error: {r2.text[:200]}")

# Test register with valid password
import random
uname = f"e2etest{random.randint(1000,9999)}"
r3 = httpx.post(f"{BASE}/api/v1/auth/register", json={
    "username": uname,
    "email": f"{uname}@test.com",
    "password": "TestPass1!",
    "role": "freelancer"
}, timeout=5)
print(f"Register: {r3.status_code}")
if r3.status_code not in (200, 201):
    print(f"  Error: {r3.text[:300]}")

# Test register with WEAK password (should fail)
r4 = httpx.post(f"{BASE}/api/v1/auth/register", json={
    "username": "weakuser",
    "email": "weak@test.com",
    "password": "password123",
    "role": "freelancer"
}, timeout=5)
print(f"Register weak password: {r4.status_code} (expected 422)")
