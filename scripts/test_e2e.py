"""QuestionWork E2E Test - Full quest lifecycle"""
import urllib.request
import json
import time
import sys

BASE = "http://127.0.0.1:8000"
API = BASE + "/api/v1"
ts = str(int(time.time()))
passed = 0
failed = 0

def api(method, path, data=None, token=None, base_override=None):
    url = (base_override or API) + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        r = urllib.request.urlopen(req)
        raw = r.read().decode()
        try:
            return json.loads(raw), r.status
        except json.JSONDecodeError:
            return {"_raw": raw[:200]}, r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return json.loads(raw), e.code
        except json.JSONDecodeError:
            return {"_raw": raw[:200]}, e.code

def test(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}: {detail}")
    else:
        failed += 1
        print(f"  [FAIL] {name}: {detail}")

# ========= HEALTH =========
print("\n=== Health Check ===")
r, s = api("GET", "/health", base_override=BASE)
test("Health endpoint", s == 200, json.dumps(r))

# ========= REGISTER CLIENT =========
print("\n=== 1. Register Client ===")
r, s = api("POST", "/auth/register", {
    "username": f"client_{ts}",
    "email": f"client_{ts}@test.com",
    "password": "TestPass123!",
    "role": "client"
})
test("Register client", s in (200, 201), f"status={s}")
print(f"     RAW KEYS: {list(r.keys())}")
client_token = r.get("access_token", "")
client_id = r.get("user", {}).get("id", "") if r.get("user") else r.get("id", "")
print(f"     user={r.get('user', {})}, id={client_id}, token={client_token[:20]}...")

# ========= REGISTER FREELANCER =========
print("\n=== 2. Register Freelancer ===")
r, s = api("POST", "/auth/register", {
    "username": f"freelancer_{ts}",
    "email": f"freelancer_{ts}@test.com",
    "password": "TestPass123!"
})
test("Register freelancer", s in (200, 201), f"status={s}")
fl_token = r.get("access_token", "")
fl_id = r.get("user", {}).get("id", "") if r.get("user") else r.get("id", "")
print(f"     user={r.get('user', {})}, id={fl_id}, token={fl_token[:20]}...")

# ========= LOGIN =========
print("\n=== 3. Login Client ===")
r, s = api("POST", "/auth/login", {
    "username": f"client_{ts}",
    "password": "TestPass123!"
})
test("Login client", s == 200 and "access_token" in r, f"status={s}")

# ========= DUPLICATE REGISTRATION =========
print("\n=== 4. Duplicate Registration (expect failure) ===")
r, s = api("POST", "/auth/register", {
    "username": f"client_{ts}",
    "email": f"client_{ts}@test.com",
    "password": "TestPass123!"
})
test("Duplicate rejected", s in (400, 409, 422), f"status={s}, detail={r.get('detail', '')}")

# ========= CREATE QUEST =========
print("\n=== 5. Create Quest ===")
r, s = api("POST", "/quests/", {
    "title": "E2E Test Quest",
    "description": "Full lifecycle test quest for verification",
    "required_grade": "novice",
    "skills": ["Python", "Testing", "API"],
    "budget": 3000,
    "currency": "RUB"
}, client_token)
test("Create quest", s in (200, 201), f"status={s}")
quest_id = r.get("id", "")
print(f"     quest_id={quest_id}, xp_reward={r.get('xp_reward')}, status={r.get('status')}")

# ========= LIST QUESTS =========
print("\n=== 6. List Quests ===")
r, s = api("GET", "/quests/")
quest_count = r.get("total", 0) if isinstance(r, dict) else len(r)
quests_list = r.get("quests", []) if isinstance(r, dict) else r
test("List quests", s == 200 and quest_count > 0, f"total={quest_count}, returned={len(quests_list)}")

# ========= GET QUEST BY ID =========
print("\n=== 7. Get Quest by ID ===")
r, s = api("GET", f"/quests/{quest_id}")
test("Get quest", s == 200 and r.get("title") == "E2E Test Quest", f"title={r.get('title')}")

# ========= FREELANCER APPLIES =========
print("\n=== 8. Freelancer Applies ===")
r, s = api("POST", f"/quests/{quest_id}/apply", {
    "cover_letter": "I want to work on this quest! I have strong Python skills.",
    "proposed_price": 2500
}, fl_token)
test("Apply to quest", s in (200, 201), f"status={s}, msg={r.get('message', r)}")

# ========= CLIENT ASSIGNS FREELANCER =========
print("\n=== 9. Client Assigns Freelancer ===")
r, s = api("POST", f"/quests/{quest_id}/assign?freelancer_id={fl_id}", None, client_token)
quest_status = r.get("quest", {}).get("status", "")
test("Assign freelancer", s == 200 and quest_status == "in_progress", f"status={s}, quest_status={quest_status}")

# ========= FREELANCER COMPLETES QUEST =========
print("\n=== 10. Freelancer Completes Quest ===")
r, s = api("POST", f"/quests/{quest_id}/complete", None, fl_token)
test("Complete quest", s == 200, f"status={s}, xp_earned={r.get('xp_earned')}")

# ========= CLIENT CONFIRMS =========
print("\n=== 11. Client Confirms Completion ===")
r, s = api("POST", f"/quests/{quest_id}/confirm", None, client_token)
test("Confirm quest", s == 200, f"status={s}, msg={r.get('message')}")
print(f"     xp_reward={r.get('xp_reward')}, money_reward={r.get('money_reward')}")

# ========= CHECK FREELANCER PROFILE =========
print("\n=== 12. Freelancer Profile (XP check) ===")
r, s = api("GET", f"/users/{fl_id}", None, fl_token)
test("Profile loaded", s == 200 and r.get('xp') is not None, f"xp={r.get('xp')}, level={r.get('level')}, grade={r.get('grade')}")

# ========= FRONTEND CHECK =========
print("\n=== 13. Frontend Availability ===")
try:
    fr = urllib.request.urlopen("http://127.0.0.1:3000")
    test("Frontend responds", fr.status == 200, f"status={fr.status}")
except Exception as e:
    test("Frontend responds", False, str(e))

# ========= SUMMARY =========
print("\n" + "=" * 50)
print(f"  RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 50)

if failed > 0:
    sys.exit(1)
else:
    print("  ALL TESTS PASSED!")
    sys.exit(0)
