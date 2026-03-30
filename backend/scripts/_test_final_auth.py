import httpx

BASE = "http://127.0.0.1:8001"

# Test example@gmail.com login (what TestSprite AI typically uses)
r = httpx.post(f"{BASE}/api/v1/auth/login", json={"username": "example@gmail.com", "password": "password123"}, timeout=5)
print(f"example@gmail.com login: {r.status_code}")

# Test test_hero login
r2 = httpx.post(f"{BASE}/api/v1/auth/login", json={"username": "test_hero", "password": "QuestWork1!"}, timeout=5)
print(f"test_hero login: {r2.status_code}")

# Test test_hero email login  
r3 = httpx.post(f"{BASE}/api/v1/auth/login", json={"username": "test_hero@example.com", "password": "QuestWork1!"}, timeout=5)
print(f"test_hero email login: {r3.status_code}")
