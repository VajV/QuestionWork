import json
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8001/api/v1"
username = f"client_b_{int(time.time())}"
password = "TestPass123!"
email = f"{username}@example.com"

payload = {
    "username": username,
    "email": email,
    "password": password,
    "role": "client",
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    f"{BASE_URL}/auth/register",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status in (200, 201):
            print(json.dumps({"username": username, "password": password, "source": "registered"}))
            raise SystemExit(0)
        print(response.status)
        raise SystemExit(1)
except urllib.error.HTTPError as exc:
    print(json.dumps({"status": exc.code, "body": exc.read().decode("utf-8")[:500]}))
    raise SystemExit(1)
