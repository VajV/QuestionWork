import urllib.request, json, sys

BASE = "http://127.0.0.1:8000/api/v1"

def api(method, path, data=None, token=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{BASE}{path}", body)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.method = method
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

# 1. Register
print("=== Register ===")
s, d = api("POST", "/auth/register", {"username":"dbguser2","email":"dbguser2@t.com","password":"TestPass123!","role":"client"})
print(s, d)

# 2. Login
print("\n=== Login ===")
s, d = api("POST", "/auth/login", {"email":"dbguser2@t.com","password":"TestPass123!"})
print(s, d)
token = d.get("access_token","") if isinstance(d, dict) else ""

if not token:
    print("NO TOKEN, exiting")
    sys.exit(1)

# 3. Profile /users/me
print("\n=== /users/me ===")
s, d = api("GET", "/users/me", token=token)
print(s, d)

user_id = d.get("id","") if isinstance(d, dict) else ""

# 4. Profile /users/{id}
if user_id:
    print(f"\n=== /users/{user_id} ===")
    s, d = api("GET", f"/users/{user_id}", token=token)
    print(s, d)

# 5. My badges
print("\n=== /users/me/badges ===")
s, d = api("GET", "/users/me/badges", token=token)
print(s, d)

# 6. Create quest
print("\n=== Create quest ===")
quest_data = {
    "title": "Debug Quest",
    "description": "Test quest creation",
    "budget": 5000,
    "required_grade": "novice",
    "skills": ["python"]
}
s, d = api("POST", "/quests", quest_data, token=token)
print(s, d)

# 7. List quests
print("\n=== List quests ===")
s, d = api("GET", "/quests", token=token)
print(s, type(d), str(d)[:300])
