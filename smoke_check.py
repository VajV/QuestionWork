"""Quick smoke test for public API endpoints."""
import urllib.request
import urllib.error

endpoints = [
    ("GET", "http://127.0.0.1:8001/health", 200),
    ("GET", "http://127.0.0.1:8001/api/v1/quests/", 200),
    ("GET", "http://127.0.0.1:8001/api/v1/users/", 200),
    ("GET", "http://127.0.0.1:8001/api/v1/events", 200),
    ("GET", "http://127.0.0.1:8001/api/v1/badges/catalogue", 200),
    ("GET", "http://127.0.0.1:8001/api/v1/marketplace/talent", 200),
    ("GET", "http://127.0.0.1:8001/api/v1/meta/world", 200),
    ("GET", "http://127.0.0.1:8001/api/v1/classes/", 401),  # requires auth
    ("GET", "http://127.0.0.1:8001/api/v1/notifications/", 401),  # requires auth
]

ok = 0
fail = 0
for method, url, expected in endpoints:
    path = url.split("8001")[1]
    try:
        r = urllib.request.urlopen(url, timeout=10)
        status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as e:
        print(f"ERR {method} {path} -> {e}")
        fail += 1
        continue
    if status == expected:
        print(f"OK  {method} {path} -> {status}")
        ok += 1
    else:
        print(f"FAIL {method} {path} -> {status} (expected {expected})")
        fail += 1

print(f"\n--- {ok} OK, {fail} FAIL ---")
