"""QuestionWork E2E Test - Full quest lifecycle"""
import os
import urllib.request
import json
import time
import sys

BASE = "http://127.0.0.1:8001"
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

# ========= LOGIN ADMIN =========
print("\n=== 0. Login Admin ===")
r, s = api("POST", "/auth/login", {
    "username": "admin",
    "password": os.environ.get("ADMIN_PASSWORD", "Admin123!")
})
test("Login admin", s == 200 and "access_token" in r, f"status={s}")
admin_token = r.get("access_token", "")

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

# ========= FUND CLIENT WALLET =========
print("\n=== 1.1 Fund Client Wallet ===")
r, s = api("POST", f"/admin/users/{client_id}/adjust-wallet", {
    "amount": 5000,
    "currency": "RUB",
    "reason": "E2E escrow funding"
}, admin_token)
test("Fund client wallet", s == 200, f"status={s}")

r, s = api("GET", "/wallet/balance", None, client_token)
balances = r.get("balances", []) if isinstance(r, dict) else []
rub_balance = next((b.get("balance") for b in balances if b.get("currency") == "RUB"), None)
test("Client wallet funded", s == 200 and rub_balance is not None and float(rub_balance) >= 3000, f"status={s}, balance={rub_balance}")

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

# ========= CREATE DRAFT QUEST =========
print("\n=== 5. Create Draft Quest ===")
r, s = api("POST", "/quests/", {
    "title": "E2E Test Quest",
    "description": "Full lifecycle test quest for verification",
    "required_grade": "novice",
    "skills": ["Python", "Testing", "API"],
    "budget": 3000,
    "currency": "RUB",
    "status": "draft"
}, client_token)
test("Create draft quest", s in (200, 201) and r.get("status") == "draft", f"status={s}")
quest_id = r.get("id", "")
print(f"     quest_id={quest_id}, xp_reward={r.get('xp_reward')}, status={r.get('status')}")

# ========= DRAFT HIDDEN FROM PUBLIC =========
print("\n=== 6. Draft Hidden From Public Feed ===")
r, s = api("GET", "/quests/")
quest_count = r.get("total", 0) if isinstance(r, dict) else len(r)
quests_list = r.get("quests", []) if isinstance(r, dict) else r
draft_visible = any(q.get("id") == quest_id for q in quests_list)
test("Draft hidden from public feed", s == 200 and not draft_visible, f"total={quest_count}, visible={draft_visible}")

# ========= PUBLISH DRAFT =========
print("\n=== 7. Publish Draft ===")
r, s = api("POST", f"/quests/{quest_id}/publish", None, client_token)
published_status = r.get("quest", {}).get("status", "")
test("Publish draft", s == 200 and published_status == "open", f"status={s}, quest_status={published_status}")

# ========= GET QUEST HISTORY =========
print("\n=== 8. Get Quest History ===")
r, s = api("GET", f"/quests/{quest_id}/history", None, client_token)
history = r.get("history", []) if isinstance(r, dict) else []
has_publish_transition = any(h.get("from_status") == "draft" and h.get("to_status") == "open" for h in history)
test("Quest history includes publish", s == 200 and has_publish_transition, f"status={s}, entries={len(history)}")

# ========= GET QUEST BY ID =========
print("\n=== 9. Get Quest by ID ===")
r, s = api("GET", f"/quests/{quest_id}")
test("Get quest", s == 200 and r.get("title") == "E2E Test Quest", f"title={r.get('title')}")

# ========= FREELANCER APPLIES =========
print("\n=== 10. Freelancer Applies ===")
r, s = api("POST", f"/quests/{quest_id}/apply", {
    "cover_letter": "I want to work on this quest! I have strong Python skills.",
    "proposed_price": 2500
}, fl_token)
test("Apply to quest", s in (200, 201), f"status={s}, msg={r.get('message', r)}")

# ========= CLIENT ASSIGNS FREELANCER =========
print("\n=== 11. Client Assigns Freelancer ===")
r, s = api("POST", f"/quests/{quest_id}/assign?freelancer_id={fl_id}", None, client_token)
quest_status = r.get("quest", {}).get("status", "")
test("Assign freelancer", s == 200 and quest_status == "assigned", f"status={s}, quest_status={quest_status}")

r, s = api("GET", "/messages/dialogs", None, fl_token)
dialogs = r.get("dialogs", []) if isinstance(r, dict) else []
quest_dialog = next((d for d in dialogs if d.get("quest_id") == quest_id), None)
test("Dialogs list after assign", s == 200 and quest_dialog is not None and quest_dialog.get("unread_count", 0) >= 1, f"status={s}, dialogs={len(dialogs)}")

# ========= FREELANCER STARTS QUEST =========
print("\n=== 12. Freelancer Starts Quest ===")
r, s = api("POST", f"/quests/{quest_id}/start", None, fl_token)
quest_status = r.get("quest", {}).get("status", "")
test("Start quest", s == 200 and quest_status == "in_progress", f"status={s}, quest_status={quest_status}")

# ========= FREELANCER COMPLETES QUEST =========
print("\n=== 13. Freelancer Completes Quest ===")
r, s = api("POST", f"/quests/{quest_id}/complete", {
    "delivery_note": "Completed the task, attached repository and deployment notes.",
    "delivery_url": "https://example.com/e2e-result"
}, fl_token)
test("Complete quest", s == 200, f"status={s}, xp_earned={r.get('xp_earned')}")

# ========= CLIENT REQUESTS REVISION =========
print("\n=== 14. Client Requests Revision ===")
r, s = api("POST", f"/quests/{quest_id}/request-revision", {
    "revision_reason": "Please add launch steps, clarify deployment notes, and update README."
}, client_token)
quest_status = r.get("quest", {}).get("status", "")
test("Request revision", s == 200 and quest_status == "revision_requested", f"status={s}, quest_status={quest_status}")

r, s = api("GET", "/messages/dialogs", None, fl_token)
dialogs = r.get("dialogs", []) if isinstance(r, dict) else []
quest_dialog = next((d for d in dialogs if d.get("quest_id") == quest_id), None)
dialog_unread = quest_dialog.get("unread_count", 0) if quest_dialog else 0
test("Dialogs unread after revision", s == 200 and dialog_unread >= 1, f"status={s}, unread={dialog_unread}")

r, s = api("GET", f"/messages/{quest_id}", None, fl_token)
messages = r.get("messages", []) if isinstance(r, dict) else []
system_count = len([m for m in messages if m.get("message_type") == "system"])
test("Chat history includes system messages", s == 200 and system_count >= 3, f"status={s}, system_count={system_count}, unread={r.get('unread_count')}")

# ========= FREELANCER RESUBMITS =========
print("\n=== 15. Freelancer Resubmits Quest ===")
r, s = api("POST", f"/quests/{quest_id}/complete", {
    "delivery_note": "Updated README, added launch steps, and clarified deployment notes.",
    "delivery_url": "https://example.com/e2e-result-v2"
}, fl_token)
quest_status = r.get("quest", {}).get("status", "")
test("Resubmit quest", s == 200 and quest_status == "completed", f"status={s}, quest_status={quest_status}")

# ========= CLIENT CONFIRMS =========
print("\n=== 16. Client Confirms Completion ===")
r, s = api("POST", f"/quests/{quest_id}/confirm", None, client_token)
test("Confirm quest", s == 200, f"status={s}, msg={r.get('message')}")
print(f"     xp_reward={r.get('xp_reward')}, money_reward={r.get('money_reward')}")

# ========= CLIENT LEAVES REVIEW =========
print("\n=== 17. Client Leaves Review ===")
r, s = api("GET", f"/reviews/check/{quest_id}", None, client_token)
test("Review status before submit", s == 200 and r.get("has_reviewed") is False, f"status={s}, has_reviewed={r.get('has_reviewed')}")

r, s = api("POST", "/reviews/", {
    "quest_id": quest_id,
    "reviewee_id": fl_id,
    "rating": 5,
    "comment": "Excellent delivery, quick revisions, and clear communication."
}, client_token)
test("Create review", s == 201 and r.get("reviewee_id") == fl_id, f"status={s}, xp_bonus={r.get('xp_bonus')}")

r, s = api("GET", f"/reviews/check/{quest_id}", None, client_token)
test("Review status after submit", s == 200 and r.get("has_reviewed") is True, f"status={s}, has_reviewed={r.get('has_reviewed')}")

r, s = api("GET", f"/reviews/user/{fl_id}")
reviews = r.get("reviews", []) if isinstance(r, dict) else []
test("Freelancer reviews available", s == 200 and len(reviews) >= 1, f"status={s}, reviews={len(reviews)}")

# ========= CHECK FREELANCER PROFILE =========
print("\n=== 18. Freelancer Profile (XP check) ===")
r, s = api("GET", f"/users/{fl_id}", None, fl_token)
test("Profile loaded", s == 200 and r.get('xp') is not None, f"xp={r.get('xp')}, level={r.get('level')}, grade={r.get('grade')}")

# ========= FRONTEND CHECK =========
print("\n=== 19. Frontend Availability ===")
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
