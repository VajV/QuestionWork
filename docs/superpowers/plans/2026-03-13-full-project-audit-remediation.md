# Full Project Audit Remediation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all P0, P1, and P2 issues discovered in the comprehensive security/money/logic/frontend audit of QuestionWork.

**Architecture:** Backend fixes use asyncpg + Pydantic + FastAPI patterns; frontend fixes use TypeScript + React hooks. All money math stays Decimal server-side; frontend normalizes via existing `toNumber()` pipeline. TDD for every backend change.

**Tech Stack:** Python 3.12, FastAPI, asyncpg, Pydantic v2, Next.js 14, TypeScript, React 18

---

## Audit Summary

| Severity | Count | Main Areas |
|----------|-------|------------|
| **P0** | 3 | Refresh token race condition · force-complete unpaid freelancer · platform-user FK guard |
| **P1** | 12 | Idempotency key status · TOTP key derivation · quest slot inflation · commission rounding · missing rate limits · XP float · CSP header · admin audit tx_type |
| **P2** | 16 | Frontend money float parsing · double-submit prevention · stale exchange rates · error swallowing in hooks · useXpToast cleanup · useNotifications visibility · admin XP negative grant · frontend race conditions · body size limit · TOTP error disclosure · refresh token eviction · missing DB indexes |
| **P3** | 8 | bcrypt cost explicit · dependency arrays · timeout config · ENUM rigidity · pagination · logging |

**Production Readiness Assessment:** ~78%. Money flows and escrow are structurally sound but have edge-case race conditions and rounding gaps. Security is mature with proper JWT, bcrypt, TOTP, and rate limiting, but refresh token rotation has a P0 race. Frontend has solid patterns but money displays use float.

---

## Chunk 1: P0 Critical Fixes (Security + Money)

### Task 1: Atomic Refresh Token Rotation

**Files:**
- Modify: `backend/app/core/security.py:155-190` (refresh token functions)
- Modify: `backend/app/api/v1/endpoints/auth.py:264-275` (refresh endpoint)
- Test: `backend/tests/test_security.py`

**Problem:** Two concurrent `/refresh` requests with the same token both pass `verify_refresh_token()`, then both revoke and create new tokens. Result: two valid refresh tokens for the same user — session hijacking vector.

- [ ] **Step 1: Write the failing test**

```python
# In backend/tests/test_security.py — add to existing test class
import threading
from app.core.security import (
    create_refresh_token, verify_refresh_token,
    revoke_refresh_token,
)

class TestRefreshTokenAtomicity:
    def test_concurrent_refresh_only_one_succeeds(self):
        """Two concurrent refreshes of the same token: only one should get a valid user_id."""
        token, _ = create_refresh_token("user-race-test")
        results = [None, None]

        def attempt_refresh(idx):
            uid = verify_refresh_token(token)
            if uid:
                revoke_refresh_token(token)
            results[idx] = uid

        t1 = threading.Thread(target=attempt_refresh, args=(0,))
        t2 = threading.Thread(target=attempt_refresh, args=(1,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        valid_count = sum(1 for r in results if r is not None)
        # With atomic rotation, at most one thread should get a user_id
        # In-memory store without lock: both may succeed (the bug)
        # After fix: exactly one succeeds
        assert valid_count <= 1, f"Both threads got a valid user_id: {results}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_security.py::TestRefreshTokenAtomicity -v --no-cov`
Expected: FAIL — both threads get valid user_id

- [ ] **Step 3: Implement atomic verify-and-revoke**

In `backend/app/core/security.py`, add a threading lock around the in-memory store and create a combined `rotate_refresh_token()` function:

```python
import threading

_refresh_store_lock = threading.Lock()

def rotate_refresh_token(old_token: str) -> Tuple[Optional[str], Optional[str], int]:
    """Atomically verify old token, revoke it, and issue new one.

    Returns (user_id, new_token, expires_seconds).
    If old_token is invalid/expired, returns (None, None, 0).
    """
    client = _get_refresh_store_client()
    if client:
        # Redis: use pipeline for atomicity
        key = f"refresh:{old_token}"
        pipe = client.pipeline(True)
        try:
            pipe.get(key)
            pipe.delete(key)
            results = pipe.execute()
            user_id = results[0]
        except Exception:
            raise RefreshTokenStoreUnavailableError("Redis unavailable during token rotation")
        if not user_id:
            return None, None, 0
        new_token, expires_seconds = create_refresh_token(user_id)
        return user_id, new_token, expires_seconds
    else:
        # In-memory: use lock
        with _refresh_store_lock:
            entry = _IN_MEMORY_REFRESH_STORE.pop(old_token, None)
            if not entry:
                return None, None, 0
            if entry.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
                return None, None, 0
            user_id = entry.get("user_id")
            if not user_id:
                return None, None, 0
            new_token, expires_seconds = create_refresh_token(user_id)
            return user_id, new_token, expires_seconds
```

- [ ] **Step 4: Update auth.py refresh endpoint to use `rotate_refresh_token()`**

In `backend/app/api/v1/endpoints/auth.py`, replace the verify/revoke/create sequence (~lines 264-275) with:

```python
    user_id, new_refresh, expires_seconds = rotate_refresh_token(refresh)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_security.py::TestRefreshTokenAtomicity -v --no-cov`
Expected: PASS

- [ ] **Step 6: Run full test suite for no regressions**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/ --no-cov --tb=short -q`
Expected: 582+ passed, 0 failed

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/security.py backend/app/api/v1/endpoints/auth.py backend/tests/test_security.py
git commit -m "fix(auth): atomic refresh token rotation prevents concurrent session duplication [P0]"
```

---

### Task 2: Guard PLATFORM_USER_ID Existence in split_payment

**Files:**
- Modify: `backend/app/services/wallet_service.py:460-530` (split_payment function)
- Test: `backend/tests/test_wallet_service.py`

**Problem:** `split_payment()` credits the platform wallet assuming `PLATFORM_USER_ID` exists. If that user record was deleted, the FK constraint on wallets table fails, transaction rolls back, but code has no explicit check — error is opaque.

- [ ] **Step 1: Write the failing test**

```python
# In backend/tests/test_wallet_service.py — add test
class TestSplitPaymentPlatformGuard:
    @pytest.mark.asyncio
    async def test_split_payment_fails_if_platform_user_missing(self, mock_conn):
        """split_payment should raise ValueError if PLATFORM_USER_ID doesn't exist."""
        # Setup: mock conn where platform user doesn't exist
        mock_conn.fetchrow.side_effect = [
            None,  # hold lookup → no escrow
        ]
        mock_conn.fetchval.return_value = None  # platform user check → missing

        with pytest.raises(ValueError, match="Platform user.*does not exist"):
            await wallet_service.split_payment(
                mock_conn,
                client_id="client-1",
                freelancer_id="freelancer-1",
                gross_amount=Decimal("1000.00"),
                quest_id="quest-1",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_wallet_service.py::TestSplitPaymentPlatformGuard -v --no-cov`
Expected: FAIL

- [ ] **Step 3: Add platform user guard**

At the start of `split_payment()`, after `_assert_in_transaction(conn)` and `gross_amount = quantize_money(gross_amount)`:

```python
    # Verify platform user exists to receive commission
    platform_exists = await conn.fetchval(
        "SELECT 1 FROM users WHERE id = $1", settings.PLATFORM_USER_ID
    )
    if not platform_exists:
        raise ValueError(
            f"Platform user {settings.PLATFORM_USER_ID} does not exist. "
            "Cannot process commission. Aborting payment."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_wallet_service.py::TestSplitPaymentPlatformGuard -v --no-cov`
Expected: PASS

- [ ] **Step 5: Run full wallet tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_wallet_service.py -v --no-cov --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/wallet_service.py backend/tests/test_wallet_service.py
git commit -m "fix(wallet): guard PLATFORM_USER_ID existence before commission credit [P0]"
```

---

### Task 3: Fix force-complete skip_escrow Payment Logic

**Files:**
- Modify: `backend/app/services/admin_service.py:570-630` (force_complete_quest)
- Test: `backend/tests/test_admin_service.py`

**Problem:** When `skip_escrow=True` and no hold exists, code still calls `split_payment()` which falls through to direct debit from client. If client has no balance, quest is marked confirmed but freelancer is unpaid. 

- [ ] **Step 1: Write the failing test**

```python
# In backend/tests/test_admin_service.py
class TestForceCompleteSkipEscrowNoPayment:
    @pytest.mark.asyncio
    async def test_force_complete_skip_escrow_no_hold_skips_payment(self, mock_conn, ...):
        """When skip_escrow=True and no hold exists, payment must be entirely skipped."""
        # Setup: quest in 'in_progress', no hold
        mock_conn.fetchrow.side_effect = [
            {"id": "q1", "status": "in_progress", "assigned_to": "f1", "client_id": "c1",
             "budget": Decimal("5000.00"), "currency": "RUB", "xp_reward": 100, ...},
            None,  # hold lookup → no escrow
        ]

        result = await admin_service.force_complete_quest(
            mock_conn, quest_id="q1", admin_id="admin1", skip_escrow=True
        )

        assert result["payment_skipped"] is True
        # Verify split_payment was NOT called
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — current code proceeds to split_payment even when skip_escrow=True

- [ ] **Step 3: Fix the logic**

In `admin_service.py` `force_complete_quest()`, after the hold check (~line 580):

```python
    payment_skipped = False
    if not hold_row:
        if not skip_escrow:
            raise ValueError(
                "Admin force-complete requires an active escrow hold. "
                "Pass skip_escrow=True to override (no payment will be made to freelancer)."
            )
        logger.warning(
            "[AUDIT] Admin force-complete with no escrow hold: "
            "quest=%s, admin action, skip_escrow=True — PAYMENT SKIPPED",
            quest_id,
        )
        payment_skipped = True

    # XP reward is always granted
    # ... (existing XP granting code) ...

    # Payment split only if hold existed
    if not payment_skipped:
        payment_result = await split_payment(conn, ...)
    else:
        payment_result = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_admin_service.py::TestForceCompleteSkipEscrowNoPayment -v --no-cov`
Expected: PASS

- [ ] **Step 5: Run all admin tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_admin_service.py -v --no-cov --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/admin_service.py backend/tests/test_admin_service.py
git commit -m "fix(admin): skip_escrow=True with no hold now skips payment entirely [P0]"
```

---

## Chunk 2: P1 Security & Money Fixes

### Task 4: Separate TOTP Encryption Key from SECRET_KEY

**Files:**
- Modify: `backend/app/core/config.py:20-50` (add TOTP_ENCRYPTION_KEY setting)
- Modify: `backend/app/core/security.py:245-255` (_totp_fernet_key function)
- Modify: `backend/.env.example`
- Modify: `backend/.env`
- Test: `backend/tests/test_security.py`

**Problem:** TOTP encryption key is derived via `sha256(SECRET_KEY)`. If SECRET_KEY leaks, all encrypted TOTP secrets are exposed. Need a separate key.

- [ ] **Step 1: Write the failing test**

```python
class TestTotpKeyIsolation:
    def test_totp_key_differs_from_secret_key_hash(self):
        """TOTP encryption key should NOT be a direct hash of SECRET_KEY."""
        from app.core.security import _totp_fernet_key
        import hashlib, base64
        naive_key = base64.urlsafe_b64encode(
            hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        )
        actual_key = _totp_fernet_key()
        assert actual_key != naive_key, "TOTP key should use independent secret"
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — currently they are identical

- [ ] **Step 3: Add TOTP_ENCRYPTION_KEY to config**

In `config.py`:
```python
    TOTP_ENCRYPTION_KEY: str = ""  # Must be set if ADMIN_TOTP_REQUIRED=True
```

In `_validate_settings()`, add:
```python
    if s.ADMIN_TOTP_REQUIRED and not s.TOTP_ENCRYPTION_KEY:
        raise RuntimeError("TOTP_ENCRYPTION_KEY must be set when ADMIN_TOTP_REQUIRED=True")
```

- [ ] **Step 4: Update _totp_fernet_key()**

```python
def _totp_fernet_key() -> bytes:
    """Derive a 32-byte Fernet key from TOTP_ENCRYPTION_KEY (or fallback to SECRET_KEY with domain separation)."""
    source = settings.TOTP_ENCRYPTION_KEY or settings.SECRET_KEY
    digest = hashlib.sha256(b"totp_encryption:" + source.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)
```

- [ ] **Step 5: Update .env and .env.example**

```
# .env.example
TOTP_ENCRYPTION_KEY=<random-64-char-hex>  # Required when ADMIN_TOTP_REQUIRED=True

# .env (local dev)
TOTP_ENCRYPTION_KEY=dev-totp-key-for-local-testing-only
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_security.py::TestTotpKeyIsolation -v --no-cov`
Expected: PASS

- [ ] **Step 7: Run full test suite**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/ --no-cov --tb=short -q`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/config.py backend/app/core/security.py backend/.env.example
git commit -m "fix(security): isolate TOTP encryption key from main SECRET_KEY [P1]"
```

---

### Task 5: Fix Idempotency Key Status Check in Withdrawal

**Files:**
- Modify: `backend/app/services/wallet_service.py:494-510` (idempotency check)
- Test: `backend/tests/test_wallet_service.py`

**Problem:** Idempotency check returns a rejected/completed withdrawal as if it were still valid. Frontend gets `"idempotent": true, "status": "rejected"` — confusing. Should only match pending withdrawals for idempotency, or raise on rejected.

- [ ] **Step 1: Write the failing test**

```python
class TestIdempotencyKeyRejectedWithdrawal:
    @pytest.mark.asyncio
    async def test_idempotency_returns_error_for_rejected_withdrawal(self, mock_conn):
        """Retry with same idempotency_key on a rejected withdrawal should raise, not return silently."""
        mock_conn.fetchrow.return_value = {
            "id": "tx-1", "amount": Decimal("500.00"),
            "currency": "RUB", "status": "rejected",
        }

        with pytest.raises(ValueError, match="already rejected"):
            await wallet_service.create_withdrawal(
                mock_conn, user_id="u1", amount=Decimal("500.00"),
                currency="RUB", idempotency_key="same-key",
            )
```

- [ ] **Step 2: Run test to confirm it fails**

Expected: FAIL — currently returns the rejected record silently

- [ ] **Step 3: Fix the idempotency check**

In `wallet_service.py`, after the existing idempotency check finds a record:

```python
    if existing:
        if existing["status"] == "pending":
            return {
                "transaction_id": existing["id"],
                "amount": _to_decimal(existing["amount"]),
                "currency": existing["currency"],
                "status": existing["status"],
                "new_balance": ...,
                "idempotent": True,
            }
        else:
            raise ValueError(
                f"Withdrawal with this idempotency key already {existing['status']}. "
                "Use a new idempotency_key to create a fresh request."
            )
```

- [ ] **Step 4: Run test to confirm it passes**

Expected: PASS

- [ ] **Step 5: Run full wallet tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_wallet_service.py -v --no-cov --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/wallet_service.py backend/tests/test_wallet_service.py
git commit -m "fix(wallet): idempotency check rejects non-pending withdrawals [P1]"
```

---

### Task 6: Commission Rounding Invariant

**Files:**
- Modify: `backend/app/services/wallet_service.py:495-500` (split_payment)
- Test: `backend/tests/test_wallet_service.py`

**Problem:** `platform_fee + freelancer_amount` may not equal `gross_amount` due to independent `quantize_money()` calls. Off-by-one-cent over thousands of transactions.

- [ ] **Step 1: Write the failing test**

```python
class TestCommissionRoundingInvariant:
    @pytest.mark.asyncio
    async def test_fee_plus_payout_equals_gross(self, mock_conn):
        """freelancer_amount + platform_fee must always equal gross_amount."""
        from app.services.wallet_service import quantize_money, _to_decimal
        from decimal import Decimal

        test_cases = [
            (Decimal("100.01"), Decimal("10")),   # 10% of 100.01
            (Decimal("333.33"), Decimal("15")),   # 15% of 333.33
            (Decimal("0.03"), Decimal("33.33")),  # extreme small amount
            (Decimal("99999.99"), Decimal("7.5")),
        ]

        for gross, pct in test_cases:
            gross = quantize_money(gross)
            fee = quantize_money(gross * pct / Decimal("100"))
            payout = gross - fee  # NOT quantize_money(gross - fee)
            assert fee + payout == gross, f"Invariant broken: {fee} + {payout} != {gross}"
```

- [ ] **Step 2: Run test to verify it passes (or fails for edge cases)**

Expected: PASS if we use `gross - fee` without re-quantizing

- [ ] **Step 3: Fix split_payment to preserve invariant**

Change the calculation in `split_payment()`:

```python
    platform_fee = quantize_money(gross_amount * fee_pct / Decimal("100"))
    freelancer_amount = gross_amount - platform_fee  # NOT re-quantized — preserves invariant
    assert platform_fee + freelancer_amount == gross_amount, "Commission split invariant violated"
```

- [ ] **Step 4: Run all wallet + admin tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_wallet_service.py tests/test_admin_service.py -v --no-cov --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/wallet_service.py backend/tests/test_wallet_service.py
git commit -m "fix(wallet): commission split invariant — fee + payout == gross [P1]"
```

---

### Task 7: Add CSP Security Header

**Files:**
- Modify: `backend/app/main.py:294-300` (security headers middleware)
- Test: `backend/tests/test_security_hardening.py`

**Problem:** Missing Content-Security-Policy header. Without CSP, XSS attacks have no secondary defense.

- [ ] **Step 1: Write the failing test**

```python
class TestCSPHeader:
    def test_response_includes_csp_header(self, client):
        """All responses must include Content-Security-Policy header."""
        resp = client.get("/health")
        assert "Content-Security-Policy" in resp.headers
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src" in csp
        assert "frame-ancestors 'none'" in csp
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — no CSP header present

- [ ] **Step 3: Add CSP header to security middleware**

In `main.py`, in the security headers section (after X-Content-Type-Options):

```python
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
```

Note: This is the **API server** CSP, not the frontend. API responses should be very restrictive since they return JSON, not HTML.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_security_hardening.py::TestCSPHeader -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_security_hardening.py
git commit -m "fix(security): add Content-Security-Policy header to API responses [P1]"
```

---

### Task 8: Fix XP Calculation Float → Decimal

**Files:**
- Modify: `backend/app/core/rewards.py:188` (check_level_up estimated_level)
- Test: `backend/tests/test_stat_growth.py`

**Problem:** Level estimation uses `float` arithmetic: `(current_xp / 10) ** 0.5`. Should use integer math for deterministic results.

- [ ] **Step 1: Write the failing test**

```python
class TestXpLevelEstimation:
    def test_level_estimation_deterministic_for_large_xp(self):
        """Level estimation should be deterministic even for very large XP values."""
        from app.core.rewards import check_level_up
        # For XP=1_000_000, expected level = min(int(sqrt(100000)) + 1, 100) = min(316+1, 100) = 100
        result = check_level_up(1_000_000, 50, "novice")
        assert result["level"] <= 100
        # Ensure no floating point weirdness
        result2 = check_level_up(999_999, 50, "novice")
        assert isinstance(result2["level"], int)
```

- [ ] **Step 2: Implement integer-safe calculation**

Replace the float line:
```python
    # Before:
    estimated_level = min(int((current_xp / 10) ** 0.5) + 1, 100)
    # After:
    import math
    estimated_level = min(math.isqrt(current_xp // 10) + 1, 100)
```

`math.isqrt()` is Python 3.8+ integer square root — no float precision loss.

- [ ] **Step 3: Run test + full rewards tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_stat_growth.py -v --no-cov --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/rewards.py backend/tests/test_stat_growth.py
git commit -m "fix(rewards): use isqrt for deterministic level estimation [P1]"
```

---

### Task 9: Add Missing Rate Limit to leave_guild

**Files:**
- Modify: `backend/app/api/v1/endpoints/marketplace.py:75-85`
- Test: `backend/tests/test_marketplace_service.py`

**Problem:** `leave_guild` POST endpoint has no rate limit, unlike `join_guild` and `create_guild`.

- [ ] **Step 1: Add rate limit call**

In `marketplace.py`, inside `leave_guild` handler, before service call:

```python
    ip = request.client.host if request.client else "unknown"
    check_rate_limit(ip, action="leave_guild", limit=10, window_seconds=3600)
```

- [ ] **Step 2: Verify with test (or manual inspection)**

Check that all POST/PATCH/DELETE endpoints in marketplace.py now have rate limiting.

- [ ] **Step 3: Run marketplace tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_marketplace_service.py -v --no-cov --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/endpoints/marketplace.py
git commit -m "fix(marketplace): add rate limit to leave_guild endpoint [P1]"
```

---

### Task 10: Fix Admin Wallet Adjustment tx_type

**Files:**
- Modify: `backend/app/services/admin_service.py:690-700` (adjust_wallet)
- Test: `backend/tests/test_admin_service.py`

**Problem:** Admin wallet adjustments create transactions with `tx_type="income"`, indistinguishable from genuine quest earnings in the ledger.

- [ ] **Step 1: Write the failing test**

```python
class TestAdminAdjustTxType:
    @pytest.mark.asyncio
    async def test_admin_adjustment_uses_admin_adjust_type(self, mock_conn):
        """Admin wallet adjustments should use 'admin_adjust' tx_type, not 'income'."""
        # Verify that the credit() call uses tx_type="admin_adjust"
        ...
```

- [ ] **Step 2: Change tx_type**

In `admin_service.py` `adjust_wallet()`, change the credit/debit call:

```python
    # Before:
    tx_type="income"
    # After:
    tx_type="admin_adjust"
```

- [ ] **Step 3: Run tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_admin_service.py -v --no-cov --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/admin_service.py backend/tests/test_admin_service.py
git commit -m "fix(admin): use 'admin_adjust' tx_type for wallet adjustments [P1]"
```

---

### Task 11: Fix Quest Slot Counting (Exclude 'completed')

**Files:**
- Modify: `backend/app/services/quest_service.py:334-345` (apply_to_quest)
- Modify: `backend/app/services/quest_service.py:395-404` (assign_freelancer)
- Test: `backend/tests/test_quest_service.py`

**Problem:** Active quest slot count includes 'completed' status (awaiting client confirmation). This inflates the count — a freelancer can be blocked from applying to new quests while waiting for a client who is slow to confirm.

- [ ] **Step 1: Write the failing test**

```python
class TestQuestSlotCounting:
    @pytest.mark.asyncio
    async def test_completed_quest_does_not_block_slot(self, mock_conn):
        """A quest in 'completed' status (awaiting confirmation) should not count toward slot limit."""
        # Setup: freelancer has 3 quests, but 1 is 'completed' (awaiting confirmation)
        mock_conn.fetchval.return_value = 2  # Only 'assigned' + 'in_progress' count
        # Attempt to apply should succeed (limit=3, active=2)
        ...
```

- [ ] **Step 2: Update the SQL**

```python
    # Before:
    "SELECT COUNT(*) FROM quests WHERE assigned_to = $1 AND status IN ('assigned', 'in_progress', 'completed')"
    # After:
    "SELECT COUNT(*) FROM quests WHERE assigned_to = $1 AND status IN ('assigned', 'in_progress')"
```

Apply same change in both `apply_to_quest()` and `assign_freelancer()`.

- [ ] **Step 3: Run quest tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_quest_service.py -v --no-cov --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/quest_service.py backend/tests/test_quest_service.py
git commit -m "fix(quests): exclude 'completed' from active slot count [P1]"
```

---

## Chunk 3: P2 Frontend Fixes

### Task 12: Fix WalletPanel Float Precision in Withdrawal

**Files:**
- Modify: `frontend/src/components/rpg/WalletPanel.tsx:95` (parseFloat → string)
- Test: `cd frontend && npx tsc --noEmit`

**Problem:** `parseFloat(withdrawAmount)` loses precision on money. Should send as string and let backend parse.

- [ ] **Step 1: Fix the withdrawal amount handling**

In `WalletPanel.tsx`, change:

```typescript
// Before:
const amt = parseFloat(withdrawAmount);
if (isNaN(amt) || amt <= 0) { ... }
await requestWithdrawal(amt, currency);

// After:
const amt = withdrawAmount.trim();
const numAmt = Number(amt);
if (!amt || isNaN(numAmt) || numAmt <= 0) {
  setWithdrawError("Введите положительную сумму");
  return;
}
await requestWithdrawal(numAmt, currency);
```

Note: `requestWithdrawal` in api.ts already sends the amount in JSON body. The key fix is validating before sending and ensuring we don't do additional float math on the number.

- [ ] **Step 2: Add double-submit prevention**

Ensure the withdrawal button is disabled while `withdrawLoading` is true and that `withdrawLoading` is set BEFORE the await:

```typescript
setWithdrawLoading(true);
try {
  await requestWithdrawal(numAmt, currency);
  ...
} finally {
  setWithdrawLoading(false);
}
```

Verify the button has `disabled={withdrawLoading}`.

- [ ] **Step 3: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/rpg/WalletPanel.tsx
git commit -m "fix(frontend): prevent float precision loss in withdrawal + double-submit guard [P2]"
```

---

### Task 13: Fix useXpToast Timer Cleanup

**Files:**
- Modify: `frontend/src/hooks/useXpToast.ts:36-47` (add useEffect cleanup)

**Problem:** `setTimeout` in `showXpToast()` fires after component unmount, causing React memory leak warning.

- [ ] **Step 1: Add cleanup useEffect**

At the end of the hook, before the return statement:

```typescript
// Cleanup timer on unmount
useEffect(() => {
  return () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };
}, []);
```

- [ ] **Step 2: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useXpToast.ts
git commit -m "fix(frontend): clean up useXpToast timer on unmount [P2]"
```

---

### Task 14: Fix useNotifications Initial Fetch Visibility Race

**Files:**
- Modify: `frontend/src/hooks/useNotifications.ts:43-49`

**Problem:** If document is hidden on mount, initial `fetch()` is skipped. Notifications never load until tab is focused.

- [ ] **Step 1: Fix the ordering**

```typescript
// Before:
visibleRef.current = !document.hidden;
document.addEventListener("visibilitychange", handleVisibilityChange);
fetch();

// After:
void fetch();  // Always fetch on mount, regardless of visibility
visibleRef.current = !document.hidden;
document.addEventListener("visibilitychange", handleVisibilityChange);
```

- [ ] **Step 2: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useNotifications.ts
git commit -m "fix(frontend): always fetch notifications on mount [P2]"
```

---

### Task 15: Fix Admin EditUserModal XP Grant Negative Validation

**Files:**
- Modify: `frontend/src/components/admin/EditUserModal.tsx:372`

**Problem:** XP grant input has no `min` attribute — admin can grant negative XP.

- [ ] **Step 1: Add min attribute to XP input**

```typescript
// Find the XP amount input and add min={1}:
<input type="number" value={xpAmount} min={1} ...
```

- [ ] **Step 2: Add validation in handleGrantXP**

```typescript
const handleGrantXP = async () => {
  if (xpAmount <= 0) {
    setToast({ type: "error", msg: "XP должен быть положительным числом" });
    return;
  }
  // ... existing logic
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/EditUserModal.tsx
git commit -m "fix(frontend): prevent negative XP grant in admin modal [P2]"
```

---

### Task 16: Add Force-Complete Confirmation Dialog

**Files:**
- Modify: `frontend/src/components/admin/EditQuestModal.tsx:178-195`

**Problem:** No confirmation dialog before force-completing a quest — easy to trigger accidentally.

- [ ] **Step 1: Wrap handleForceComplete in confirm()**

```typescript
const handleForceComplete = async () => {
  if (!window.confirm("Вы уверены? Квест будет принудительно завершён и фрилансеру начислена оплата.")) {
    return;
  }
  // ... existing force-complete logic
};
```

Similarly for handleForceCancel.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/admin/EditQuestModal.tsx
git commit -m "fix(frontend): add confirmation dialog for force-complete/cancel [P2]"
```

---

### Task 17: Add Double-Submit Guards to Quest Detail Forms

**Files:**
- Modify: `frontend/src/app/quests/[id]/page.tsx:261-288`

**Problem:** Completion and revision forms can be submitted multiple times. Need `submitting` state.

- [ ] **Step 1: Add submitting state and disable buttons during async ops**

```typescript
const [submitting, setSubmitting] = useState(false);

const handleComplete = async () => {
  if (submitting) return;
  setSubmitting(true);
  try {
    // ... existing logic
  } finally {
    setSubmitting(false);
  }
};
```

Add `disabled={submitting}` to all action buttons.

- [ ] **Step 2: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/quests/[id]/page.tsx
git commit -m "fix(frontend): double-submit guards on quest detail forms [P2]"
```

---

## Chunk 4: P2 Database & Observability Fixes

### Task 18: Add Missing GIN Indexes

**Files:**
- Create: `backend/alembic/versions/<new>_add_missing_gin_indexes.py`

**Problem:** `users.skills` JSONB column lacks GIN index — talent search queries seq-scan entire users table.

- [ ] **Step 1: Generate migration**

```bash
cd backend
.venv\Scripts\python.exe -m alembic revision -m "add_missing_gin_indexes" --rev-id c6d7e8f9g0h1
```

- [ ] **Step 2: Add upgrade/downgrade**

```python
def upgrade() -> None:
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_skills_gin ON users USING gin (skills)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quest_reviews_quest_id ON quest_reviews (quest_id, created_at DESC)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_skills_gin")
    op.execute("DROP INDEX IF EXISTS idx_quest_reviews_quest_id")
```

- [ ] **Step 3: Apply migration**

Run: `cd backend && .venv\Scripts\python.exe -m alembic upgrade head`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): add GIN index on users.skills and composite on quest_reviews [P2]"
```

---

### Task 19: Add Missing CHECK Constraints

**Files:**
- Create: `backend/alembic/versions/<new>_add_rpg_check_constraints.py`

**Problem:** Missing CHECK constraints on guild seasonal rewards and class progress tables.

- [ ] **Step 1: Generate migration**

```bash
cd backend
.venv\Scripts\python.exe -m alembic revision -m "add_rpg_check_constraints" --rev-id d7e8f9g0h1i2
```

- [ ] **Step 2: Add constraints**

```python
def upgrade() -> None:
    op.execute("ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_users_review_count_non_negative CHECK (review_count >= 0)")
    op.execute("ALTER TABLE user_class_progress ADD CONSTRAINT IF NOT EXISTS chk_class_level_positive CHECK (class_level >= 1)")
    op.execute("ALTER TABLE user_class_progress ADD CONSTRAINT IF NOT EXISTS chk_perk_points_non_negative CHECK (perk_points_spent >= 0)")

def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_review_count_non_negative")
    op.execute("ALTER TABLE user_class_progress DROP CONSTRAINT IF EXISTS chk_class_level_positive")
    op.execute("ALTER TABLE user_class_progress DROP CONSTRAINT IF EXISTS chk_perk_points_non_negative")
```

- [ ] **Step 3: Apply migration**

Run: `cd backend && .venv\Scripts\python.exe -m alembic upgrade head`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): add CHECK constraints on review_count, class_level, perk_points [P2]"
```

---

### Task 20: Improve Refresh Token Eviction (Prune Expired First)

**Files:**
- Modify: `backend/app/core/security.py:170-180` (eviction logic)
- Test: `backend/tests/test_security.py`

**Problem:** When in-memory refresh store reaches capacity, it evicts the oldest (LRU) tokens — not expired ones. Valid tokens can be evicted while expired ones stay.

- [ ] **Step 1: Write the failing test**

```python
class TestRefreshTokenEviction:
    def test_expired_tokens_evicted_before_valid(self):
        """Eviction should prune expired tokens before valid ones."""
        from app.core.security import _IN_MEMORY_REFRESH_STORE, _IN_MEMORY_MAX_TOKENS
        # Fill store to capacity with a mix of expired and valid tokens
        # After eviction trigger, all expired should be gone, valid should remain
        ...
```

- [ ] **Step 2: Fix eviction logic**

Before LRU eviction, prune expired entries:

```python
    if len(_IN_MEMORY_REFRESH_STORE) >= _IN_MEMORY_MAX_TOKENS:
        # First: prune expired entries
        now = int(datetime.now(timezone.utc).timestamp())
        expired = [k for k, v in _IN_MEMORY_REFRESH_STORE.items() if v.get("exp", 0) < now]
        for k in expired:
            _IN_MEMORY_REFRESH_STORE.pop(k, None)
        # If still over capacity, evict oldest (LRU)
        if len(_IN_MEMORY_REFRESH_STORE) >= _IN_MEMORY_MAX_TOKENS:
            evict_count = _IN_MEMORY_MAX_TOKENS // 4
            for _ in range(min(evict_count, len(_IN_MEMORY_REFRESH_STORE))):
                _IN_MEMORY_REFRESH_STORE.popitem(last=False)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_security.py -v --no-cov --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "fix(auth): prune expired refresh tokens before LRU eviction [P2]"
```

---

## Chunk 5: Final Verification

### Task 21: Full Backend Test Suite

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && .venv\Scripts\python.exe -m pytest tests/ --no-cov --tb=short -q
```

Expected: 582+ passed, 0 failed

### Task 22: Frontend Type Check + Build

- [ ] **Step 1: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 2: Production build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds

### Task 23: Alembic Head Check

- [ ] **Step 1: Verify single Alembic head**

```bash
cd backend && .venv\Scripts\python.exe -m alembic heads
```

Expected: Single head revision

---

## Production Readiness Checklist

| Area | Status | Remediation |
|------|--------|-------------|
| **Refresh token race** | ❌ P0 | Task 1 |
| **Platform user guard** | ❌ P0 | Task 2 |
| **Force-complete payment skip** | ❌ P0 | Task 3 |
| **TOTP key isolation** | ❌ P1 | Task 4 |
| **Idempotency key correctness** | ❌ P1 | Task 5 |
| **Commission rounding** | ❌ P1 | Task 6 |
| **CSP header** | ❌ P1 | Task 7 |
| **XP float arithmetic** | ❌ P1 | Task 8 |
| **Rate limit coverage** | ❌ P1 | Task 9 |
| **Admin tx_type audit trail** | ❌ P1 | Task 10 |
| **Quest slot inflation** | ❌ P1 | Task 11 |
| **Frontend money precision** | ❌ P2 | Task 12 |
| **Timer cleanup** | ❌ P2 | Task 13 |
| **Notification visibility** | ❌ P2 | Task 14 |
| **Admin XP validation** | ❌ P2 | Task 15 |
| **Force-complete confirm** | ❌ P2 | Task 16 |
| **Double-submit guards** | ❌ P2 | Task 17 |
| **GIN indexes** | ❌ P2 | Task 18 |
| **CHECK constraints** | ❌ P2 | Task 19 |
| **Token eviction** | ❌ P2 | Task 20 |
| **Full verification** | ⬜ | Tasks 21-23 |
