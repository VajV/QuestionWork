# Full Project Audit — Fix Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all verified P0/P1/P2 issues from full-project audit across backend security, money flows, quest lifecycle, frontend contract drift, and infrastructure.

**Architecture:** Fixes are organized in priority batches — production blockers first, then security/money integrity, then contract alignment, then cleanup. Each task is self-contained and testable.

**Tech Stack:** FastAPI, asyncpg, Python 3.12, Next.js 14, TypeScript, PostgreSQL, Redis, Docker Compose

---

## Chunk 1: Backend Security & Money Integrity

### Task 1: Add security response headers middleware

**Files:**
- Modify: `backend/app/main.py`
- Test: Run existing tests + manual header check

- [x] **Step 1: Add security headers middleware to main.py**

In `backend/app/main.py`, add a middleware after CORS middleware:

```python
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.APP_ENV.lower() in ("production", "prod"):
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response
```

- [x] **Step 2: Run backend tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All tests pass

---

### Task 2: Add upper bounds to withdrawal and admin wallet adjustment amounts

**Files:**
- Modify: `backend/app/api/v1/endpoints/wallet.py` (WithdrawRequest)
- Modify: `backend/app/api/v1/endpoints/admin.py` (AdminAdjustWalletRequest)

- [x] **Step 1: Add le= bound to WithdrawRequest.amount**

In `backend/app/api/v1/endpoints/wallet.py`, change:
```python
amount: Decimal = Field(..., gt=0, description="Amount to withdraw (must be > 0)")
```
to:
```python
amount: Decimal = Field(..., gt=0, le=10_000_000, description="Amount to withdraw (must be > 0)")
```

- [x] **Step 2: Add bounds to AdminAdjustWalletRequest.amount**

In `backend/app/api/v1/endpoints/admin.py`, change:
```python
amount: Decimal = Field(..., description="Positive = credit, negative = debit")
```
to:
```python
amount: Decimal = Field(..., ge=-10_000_000, le=10_000_000, description="Positive = credit, negative = debit")
```

- [x] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All pass

---

### Task 3: Fix force_complete_quest to include badges, class XP, and stats

**Files:**
- Modify: `backend/app/services/admin_service.py` (force_complete_quest function)

- [x] **Step 1: Add badge, class XP, and stat allocation calls**

In `force_complete_quest`, after the XP update block (after `await conn.execute("UPDATE users SET xp=$1...")`), add badge and class XP calls matching `confirm_quest_completion`:

```python
            # Badge check (matching confirm_quest_completion)
            award_result = await badge_service.check_and_award(
                conn, row["assigned_to"], quest_id=quest_id,
            )

            # Class XP (matching confirm_quest_completion)
            class_result = await class_service.add_class_xp(
                conn, row["assigned_to"],
                xp_amount=xp_reward,
                source_quest_id=quest_id,
            )
```

Also add imports at top of file if not present: `badge_service`, `class_service`.

- [x] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All pass

---

### Task 4: Fix float(budget) in XP calculation — use Decimal

**Files:**
- Modify: `backend/app/core/rewards.py`

- [x] **Step 1: Replace float(budget) with Decimal conversion**

In `backend/app/core/rewards.py`, change:
```python
base_xp = int(float(budget) * XP_PER_BUDGET_RATIO)
```
to:
```python
from decimal import Decimal as _Decimal
base_xp = int(_Decimal(str(budget)) * _Decimal(str(XP_PER_BUDGET_RATIO)))
```

- [x] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All pass

---

### Task 5: Add rate limiting to users.py GET endpoints

**Files:**
- Modify: `backend/app/api/v1/endpoints/users.py`

- [x] **Step 1: Add rate limiting to list_users and get_user endpoints**

Import `check_rate_limit` and `get_client_ip` in `users.py`, then add to each GET endpoint:
```python
check_rate_limit(get_client_ip(request), action="list_users", limit=60, window_seconds=60)
```

- [x] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All pass

---

### Task 6: Add timing-safe login (dummy bcrypt on user-not-found)

**Files:**
- Modify: `backend/app/api/v1/endpoints/auth.py`

- [x] **Step 1: Add dummy bcrypt check when user not found**

In the login endpoint, when user is not found, add a dummy bcrypt call before raising the error to prevent timing oracle:

```python
if not user_row:
    # Constant-time: prevent timing oracle that reveals user existence
    import bcrypt as _bcrypt
    _bcrypt.checkpw(b"dummy_password", b"$2b$12$LJ3m4ys3Lg3lE9Q8pBkSp.ZxOXSCmRCVHaLCQ5FhCjXxVx5m5sZ6C")
    raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль")
```

- [x] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All pass

---

### Task 7: Narrow refresh cookie path to /api/v1/auth

**Files:**
- Modify: `backend/app/api/v1/endpoints/auth.py`

- [x] **Step 1: Change cookie path from "/" to "/api/v1/auth"**

In all `response.set_cookie(key="refresh_token", ...)` calls, change `path="/"` to `path="/api/v1/auth"`.

Also update `response.delete_cookie(key="refresh_token", ...)` in the logout endpoint to use `path="/api/v1/auth"`.

- [x] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All pass

---

### Task 8: Restrict CORS localhost origins to development only

**Files:**
- Modify: `backend/app/main.py`

- [x] **Step 1: Gate localhost CORS origins on APP_ENV**

In `_build_cors_origins()`, wrap the localhost additions:
```python
if settings.APP_ENV.lower() in ("development", "dev"):
    origins.update({"http://localhost:3000", "http://127.0.0.1:3000"})
```

Also gate the `allow_origin_regex` in CORS middleware setup — set it to `None` in production.

- [x] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All pass

---

## Chunk 2: Frontend Contract Fixes

### Task 9: Fix quest creation validation to match backend

**Files:**
- Modify: `frontend/src/app/quests/create/page.tsx`

- [x] **Step 1: Fix budget validation bounds**

Change:
```typescript
if (isNaN(budget) || budget <= 0)
  return "Введите корректный бюджет (больше 0)";
if (budget > 10_000_000)
  return "Бюджет слишком большой";
```
to:
```typescript
if (isNaN(budget) || budget < 100)
  return "Минимальный бюджет — 100";
if (budget > 1_000_000)
  return "Максимальный бюджет — 1 000 000";
```

- [x] **Step 2: Remove USDT from currency options**

Change:
```typescript
const CURRENCY_OPTIONS = ["RUB", "USD", "EUR", "USDT"];
```
to:
```typescript
const CURRENCY_OPTIONS = ["RUB", "USD", "EUR"];
```

- [x] **Step 3: Send budget as string to preserve precision**

Change:
```typescript
budget: parseFloat(form.budget),
```
to:
```typescript
budget: form.budget,
```

- [x] **Step 4: Fix title max length (100 → 200)**

Change validation from 100 to 200 and update `maxLength` on the input element.

- [x] **Step 5: Fix description max length (2000 → 5000)**

Change validation from 2000 to 5000 and update `maxLength` on the textarea.

- [x] **Step 6: Fix skills limit (10 → 20)**

Change:
```typescript
form.skills.length >= 10
```
to:
```typescript
form.skills.length >= 20
```

- [x] **Step 7: Run frontend type check + build**

Run: `cd frontend && npx tsc --noEmit && npx next build`
Expected: No errors

---

### Task 10: Add missing fields to frontend types

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [x] **Step 1: Add platform_fee_percent to Quest interface**

Add to `Quest` interface:
```typescript
platform_fee_percent?: number | null;
```

- [x] **Step 2: Add is_banned and banned_reason to UserProfile**

Add to `UserProfile` interface:
```typescript
is_banned: boolean;
banned_reason: string | null;
```

- [x] **Step 3: Run type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

---

### Task 11: Fix admin broadcast empty user_ids validation

**Files:**
- Modify: `frontend/src/app/admin/dashboard/page.tsx`

- [x] **Step 1: Add client-side validation for empty user_ids**

Before the API call in the broadcast handler, add:
```typescript
if (ids.length === 0) {
  setBcError("Укажите хотя бы один User ID");
  return;
}
```

- [x] **Step 2: Run type check + build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

---

## Chunk 3: Infrastructure & Schema Hardening

### Task 12: Bind Docker ports to localhost and add Redis password

**Files:**
- Modify: `docker-compose.dev.yml`

- [x] **Step 1: Bind Postgres to localhost**

Change:
```yaml
ports:
  - "5432:5432"
```
to:
```yaml
ports:
  - "127.0.0.1:5432:5432"
```

- [x] **Step 2: Bind Redis to localhost and add requirepass**

Change Redis port to `127.0.0.1:6379:6379` and add command:
```yaml
command: ["redis-server", "--requirepass", "${REDIS_PASSWORD:-devpassword123}"]
```

Also update all other Docker port mappings to bind to `127.0.0.1`.

---

### Task 13: Add DB pool min <= max validation

**Files:**
- Modify: `backend/app/core/config.py`

- [x] **Step 1: Add pool size validation to _validate_settings**

Add:
```python
if s.DB_POOL_MIN_SIZE > s.DB_POOL_MAX_SIZE:
    raise RuntimeError(
        f"DB_POOL_MIN_SIZE ({s.DB_POOL_MIN_SIZE}) must be <= DB_POOL_MAX_SIZE ({s.DB_POOL_MAX_SIZE})"
    )
```

- [x] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All pass

---

### Task 14: Add per-username login rate limiting

**Files:**
- Modify: `backend/app/api/v1/endpoints/auth.py`

- [x] **Step 1: Add per-username rate limit alongside IP rate limit**

After the existing IP-based rate limit in the login endpoint, add:
```python
check_rate_limit(f"login_user:{credentials.username}", action="login_account", limit=5, window_seconds=900)
```

- [x] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/ -q --tb=short`
Expected: All pass

---

## Verification Checklist

After all tasks complete:

- [x] Backend tests pass: `cd backend && python -m pytest tests/ -q --tb=short`
- [x] Frontend type check: `cd frontend && npx tsc --noEmit`
- [x] Frontend build: `cd frontend && npx next build`
- [x] Security headers present in responses
- [x] Budget validation aligned between frontend (100-1M) and backend
- [x] USDT removed from currency options
- [x] force_complete_quest grants badges + class XP
- [x] Withdrawal amount has upper bound
- [x] Docker ports bound to localhost
