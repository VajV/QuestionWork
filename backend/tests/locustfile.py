"""
locustfile.py — Load-test baseline for QuestionWork backend.

Run:
    locust -f backend/tests/locustfile.py --host http://localhost:8001

Or headless (CI):
    locust -f backend/tests/locustfile.py --host http://localhost:8001 \
           --users 50 --spawn-rate 10 --run-time 60s --headless

User mix (reflecting real traffic):
    70%  Anonymous / quest browsing   (ReadOnlyUser)
    20%  Authenticated freelancer     (FreelancerUser)
    10%  Authenticated client         (ClientUser)

Thresholds to watch (not enforced here — set in your CI config):
    p95 response time < 300 ms  for GET /health, /quests
    p99 response time < 1 s     for POST /auth/login
    error rate        < 0.5%
"""

import random
import string
import time
from locust import HttpUser, task, between, events


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _rand_str(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def _register_and_login(client, role: str = "freelancer") -> str | None:
    """Register a fresh user and return the JWT access token (or None on failure)."""
    username = f"lt_{_rand_str()}_{int(time.time() * 1000) % 100_000}"
    payload = {
        "username": username,
        "email": f"{username}@loadtest.example",
        "password": "LtPass1!",
        "role": role,
    }
    r = client.post("/api/v1/auth/register", json=payload, name="/auth/register")
    if r.status_code not in (200, 201):
        return None
    data = r.json()
    return data.get("access_token")


# ──────────────────────────────────────────────────────────────────────
# 1. Anonymous read-only user  (70 %)
# ──────────────────────────────────────────────────────────────────────

class ReadOnlyUser(HttpUser):
    """Simulates a visitor browsing quests without logging in."""
    weight = 7
    wait_time = between(0.5, 2.0)

    @task(5)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(10)
    def list_quests(self):
        self.client.get(
            "/api/v1/quests?limit=20&offset=0",
            name="/quests (list)",
        )

    @task(3)
    def list_quests_paginated(self):
        offset = random.choice([0, 20, 40])
        self.client.get(
            f"/api/v1/quests?limit=20&offset={offset}",
            name="/quests (paginated)",
        )

    @task(1)
    def docs_endpoint(self):
        self.client.get("/docs", name="/docs")


# ──────────────────────────────────────────────────────────────────────
# 2. Authenticated freelancer  (20 %)
# ──────────────────────────────────────────────────────────────────────

class FreelancerUser(HttpUser):
    """Simulates an authenticated freelancer browsing and applying for quests."""
    weight = 2
    wait_time = between(1.0, 3.0)

    def on_start(self):
        self.token = _register_and_login(self.client, role="freelancer")
        self.quest_ids: list[str] = []

    def _auth_headers(self) -> dict:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(8)
    def list_quests(self):
        r = self.client.get(
            "/api/v1/quests?limit=20",
            headers=self._auth_headers(),
            name="/quests (auth)",
        )
        if r.status_code == 200:
            quests = r.json().get("quests", [])
            self.quest_ids = [q["id"] for q in quests[:5]]

    @task(5)
    def view_quest(self):
        if not self.quest_ids:
            return
        qid = random.choice(self.quest_ids)
        self.client.get(
            f"/api/v1/quests/{qid}",
            headers=self._auth_headers(),
            name="/quests/{id}",
        )

    @task(3)
    def view_profile(self):
        self.client.get(
            "/api/v1/users/me",
            headers=self._auth_headers(),
            name="/users/me",
        )

    @task(2)
    def check_notifications(self):
        self.client.get(
            "/api/v1/notifications?limit=10",
            headers=self._auth_headers(),
            name="/notifications",
        )

    @task(1)
    def wallet_balance(self):
        self.client.get(
            "/api/v1/wallet/balance",
            headers=self._auth_headers(),
            name="/wallet/balance",
        )

    @task(1)
    def view_badges(self):
        self.client.get(
            "/api/v1/badges/me",
            headers=self._auth_headers(),
            name="/badges/me",
        )


# ──────────────────────────────────────────────────────────────────────
# 3. Authenticated client  (10 %)
# ──────────────────────────────────────────────────────────────────────

class ClientUser(HttpUser):
    """Simulates a client who posts quests and monitors them."""
    weight = 1
    wait_time = between(2.0, 5.0)

    def on_start(self):
        self.token = _register_and_login(self.client, role="client")
        self.my_quest_ids: list[str] = []

    def _auth_headers(self) -> dict:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(3)
    def list_my_quests(self):
        r = self.client.get(
            "/api/v1/quests?limit=10",
            headers=self._auth_headers(),
            name="/quests (client)",
        )
        if r.status_code == 200:
            quests = r.json().get("quests", [])
            self.my_quest_ids = [q["id"] for q in quests[:3]]

    @task(2)
    def create_quest(self):
        if not self.token:
            return
        payload = {
            "title": f"Load Test Quest {_rand_str(4)}",
            "description": "Automated load test quest. Please ignore.",
            "reward": round(random.uniform(50, 500), 2),
            "currency": "RUB",
            "required_level": 1,
            "tags": ["loadtest"],
        }
        r = self.client.post(
            "/api/v1/quests",
            json=payload,
            headers=self._auth_headers(),
            name="/quests (create)",
        )
        if r.status_code in (200, 201):
            created = r.json()
            if qid := created.get("id"):
                self.my_quest_ids.append(qid)

    @task(1)
    def view_quest_detail(self):
        if not self.my_quest_ids:
            return
        qid = random.choice(self.my_quest_ids)
        self.client.get(
            f"/api/v1/quests/{qid}",
            headers=self._auth_headers(),
            name="/quests/{id} (client)",
        )

    @task(1)
    def check_profile(self):
        self.client.get(
            "/api/v1/users/me",
            headers=self._auth_headers(),
            name="/users/me (client)",
        )


# ──────────────────────────────────────────────────────────────────────
# Event hooks — print quick stats summary at test end
# ──────────────────────────────────────────────────────────────────────

@events.quitting.add_listener
def _on_quit(environment, **kwargs):
    stats = environment.stats
    total = stats.total
    if total.num_requests == 0:
        return
    print(
        f"\n[Load Test Summary]\n"
        f"  Total requests : {total.num_requests}\n"
        f"  Failures       : {total.num_failures} ({total.fail_ratio * 100:.1f}%)\n"
        f"  Avg (ms)       : {total.avg_response_time:.0f}\n"
        f"  p95 (ms)       : {total.get_response_time_percentile(0.95):.0f}\n"
        f"  p99 (ms)       : {total.get_response_time_percentile(0.99):.0f}\n"
        f"  RPS            : {total.current_rps:.1f}\n"
    )
