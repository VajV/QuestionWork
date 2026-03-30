import json
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8001/api/v1"


def post(path: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def try_login(username: str, password: str):
    return post("/auth/login", {"username": username, "password": password})


def try_register(username: str, email: str, password: str):
    return post(
        "/auth/register",
        {
            "username": username,
            "email": email,
            "password": password,
            "role": "client",
        },
    )


status, body = try_login("client_user", "client123")
if status == 200:
    print(json.dumps({"username": "client_user", "password": "client123", "source": "seeded"}))
    raise SystemExit(0)

suffix = str(int(time.time()))
username = f"client_b_{suffix}"
password = "TestPass123!"
email = f"{username}@example.com"
reg_status, reg_body = try_register(username, email, password)
if reg_status == 200:
    print(json.dumps({"username": username, "password": password, "source": "registered"}))
    raise SystemExit(0)

print(json.dumps({
    "seed_login_status": status,
    "seed_login_body": body[:500],
    "register_status": reg_status,
    "register_body": reg_body[:500],
}))
raise SystemExit(1)
