# Full Quest Flow Blockers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore the real end-to-end flow `create quest -> apply -> assign -> start -> complete -> confirm` and stabilize protected-page reloads.

**Architecture:** Keep the existing fee-snapshot and escrow design. Fix the actual failure points instead of weakening the domain model: enforce DB schema compatibility at startup, make admin audit logging Decimal-safe, verify and harden escrow-backed payout behavior, and unify refresh-token rotation so reloads do not race themselves into logout.

**Tech Stack:** FastAPI, asyncpg, Alembic, PostgreSQL, Next.js 14 App Router, TypeScript.

---

## Verified Root Causes

1. `backend/app/services/quest_service.py` inserts `platform_fee_percent`, but the live DB can be missing that column. There is already an Alembic migration for it in `backend/alembic/versions/u6v7w8x9y0z1_audit_final_fixes.py`, so this is schema drift, not a reason to remove the field from code.
2. `backend/app/services/admin_service.py` writes `Decimal` values into `json.dumps(...)` inside `log_admin_action()`, which breaks `adjust_wallet()`.
3. `backend/app/services/quest_service.py` confirms quests through `wallet_service.split_payment()`. The error path you saw proves the code went through the direct debit fallback in `wallet_service.debit()` instead of consuming an existing hold. That means the specific quest being confirmed had no active escrow hold.
4. `frontend/src/context/AuthContext.tsx` and `frontend/src/lib/api.ts` both call `POST /auth/refresh`. Because the backend rotates refresh tokens on every successful refresh, concurrent refresh requests can invalidate each other and drop the UI into anonymous state on hard reload.

## Priority Order

1. Fix schema drift detection and apply migration.
2. Fix `adjust-wallet` Decimal serialization.
3. Fix and verify escrow/payout behavior around `confirm`.
4. Unify refresh-token handling on reload.
5. Re-run the full browser and API flow from a fresh quest.

### Task 1: Fail Fast on Schema Drift and Unblock Quest Creation

**Files:**
- Modify: `backend/app/db/session.py`
- Keep and validate: `backend/alembic/versions/u6v7w8x9y0z1_audit_final_fixes.py`
- Test: `backend/tests/test_quest_service.py`

**Step 1: Write the failing regression test for missing `platform_fee_percent`**

Add a test near the existing `create_quest` coverage in `backend/tests/test_quest_service.py` that proves startup/schema validation rejects a DB missing the required column with an actionable error.

```python
@pytest.mark.asyncio
async def test_schema_validation_requires_platform_fee_percent(monkeypatch):
    conn = AsyncMock()
    conn.fetchval.side_effect = [1, 0]

    with pytest.raises(RuntimeError, match="platform_fee_percent"):
        await session._validate_required_schema(conn)
```

**Step 2: Run the focused test to verify it fails**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_quest_service.py -k platform_fee_percent -q --tb=short`

Expected: fail because `_validate_required_schema()` does not exist yet.

**Step 3: Implement a startup schema guard in `backend/app/db/session.py`**

Add a helper that checks the live schema after pool creation and before serving requests.

```python
async def _validate_required_schema(conn: asyncpg.Connection) -> None:
    has_quests_table = await conn.fetchval(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'quests'
        """
    )
    if not has_quests_table:
        raise RuntimeError("Database schema is incomplete: quests table is missing")

    has_fee_column = await conn.fetchval(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'quests'
          AND column_name = 'platform_fee_percent'
        """
    )
    if not has_fee_column:
        raise RuntimeError(
            "Database schema is out of date: quests.platform_fee_percent is missing. "
            "Run Alembic migrations before starting the API."
        )
```

Call it from `init_db_pool()` using a real acquired connection immediately after pool creation.

**Step 4: Verify the migration is still the source of truth**

Do not remove `platform_fee_percent` from `create_quest()`. Keep `backend/alembic/versions/u6v7w8x9y0z1_audit_final_fixes.py` as the canonical DB fix.

Run: `cd backend; .venv\Scripts\python.exe -m alembic upgrade head`

Expected: DB upgrades cleanly and future startups no longer die on schema validation.

**Step 5: Re-run quest creation checks**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_quest_service.py -k create_quest -q --tb=short`

Expected: existing `create_quest` coverage passes.

**Step 6: Commit**

```bash
git add backend/app/db/session.py backend/tests/test_quest_service.py
git commit -m "fix: fail fast on outdated quest schema"
```

### Task 2: Make Admin Audit Logging Decimal-Safe

**Files:**
- Modify: `backend/app/services/admin_service.py`
- Test: `backend/tests/test_admin_service.py`

**Step 1: Write a failing regression test for `adjust_wallet()` audit serialization**

Add a focused test near the existing `adjust_wallet` tests in `backend/tests/test_admin_service.py`.

```python
@pytest.mark.asyncio
async def test_adjust_wallet_serializes_decimal_values_in_audit_log(monkeypatch):
    conn = AsyncMock()
    conn.fetchrow.return_value = {"id": "user_1", "username": "alice"}

    monkeypatch.setattr(wallet_service, "get_balance", AsyncMock(return_value=Decimal("100.00")))
    monkeypatch.setattr(wallet_service, "credit", AsyncMock(return_value=Decimal("150.00")))

    result = await adjust_wallet(
        conn,
        user_id="user_1",
        amount=Decimal("50.00"),
        currency="RUB",
        reason="fund test",
        admin_id="admin_1",
    )

    assert result["new_balance"] == Decimal("150.00")
```

**Step 2: Run the focused test to verify it fails**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_admin_service.py -k adjust_wallet -q --tb=short`

Expected: fail with `TypeError: Object of type Decimal is not JSON serializable`.

**Step 3: Add a recursive JSON-normalization helper in `backend/app/services/admin_service.py`**

Implement a helper used by `log_admin_action()` before `json.dumps(...)`.

```python
def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
```

Then change `log_admin_action()` to use:

```python
json.dumps(_json_safe(old_value)) if old_value is not None else None
json.dumps(_json_safe(new_value)) if new_value is not None else None
```

**Step 4: Re-run the targeted tests**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_admin_service.py -k adjust_wallet -q --tb=short`

Expected: adjust-wallet tests pass.

**Step 5: Commit**

```bash
git add backend/app/services/admin_service.py backend/tests/test_admin_service.py
git commit -m "fix: serialize decimals in admin audit logs"
```

### Task 3: Verify and Harden Escrow/Payout Behavior on Confirm

**Files:**
- Modify: `backend/app/services/quest_service.py`
- Modify if needed: `backend/app/services/wallet_service.py`
- Test: `backend/tests/test_quest_service.py`
- Test: `backend/tests/test_commission.py`

**Step 1: Write a failing escrow-backed confirmation test**

Add a test proving that a quest assigned through the normal flow consumes a held transaction at confirm time instead of debiting the client again.

```python
@pytest.mark.asyncio
async def test_confirm_quest_uses_existing_hold_before_debit(monkeypatch):
    conn = AsyncMock()
    current_user = SimpleNamespace(id="client_1")

    monkeypatch.setattr(wallet_service, "split_payment", AsyncMock(return_value={
        "freelancer_amount": Decimal("90.00"),
        "platform_fee": Decimal("10.00"),
        "client_balance": Decimal("0.00"),
        "freelancer_balance": Decimal("90.00"),
        "platform_balance": Decimal("10.00"),
    }))

    result = await quest_service.confirm_quest_completion(conn, "quest_1", current_user)

    wallet_service.split_payment.assert_awaited_once()
```

**Step 2: Add a direct test for the legacy no-hold path in `backend/tests/test_commission.py`**

Make the intended behavior explicit:

1. If a hold exists, `split_payment()` must call `release_hold()` and never call `debit()`.
2. If no hold exists, `split_payment()` may debit directly.
3. If no hold exists and client balance is too low, the service must raise `InsufficientFundsError` with a business-meaningful message.

Use mocks around `release_hold`, `debit`, and `credit` to assert the exact branch.

**Step 3: Run the focused tests to verify current behavior and find the real gap**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_commission.py tests/test_quest_service.py -k "split_payment or confirm_quest" -q --tb=short`

Expected: one of two outcomes:

1. The escrow-backed branch already passes, proving the production failure came from a legacy quest without a hold.
2. The escrow-backed branch fails, proving there is still a service-level bug to fix.

**Step 4: Implement the minimal fix based on the branch that actually fails**

Use these rules:

1. If the escrow-backed test fails, fix `wallet_service.split_payment()` or `quest_service.assign_freelancer()` so normal assign -> confirm always creates and consumes a hold.
2. If the escrow-backed test already passes, do not invent a new payout mechanism. Instead, improve the no-hold confirm path so the error is explicit and operationally recoverable.

Recommended minimal improvement for the no-hold case in `quest_service.confirm_quest_completion()`:

```python
try:
    split = await wallet_service.split_payment(...)
except InsufficientFundsError as exc:
    raise InsufficientFundsError(
        "Quest confirmation requires an active escrow hold or enough client balance for a direct debit"
    ) from exc
```

This keeps the domain rule intact and makes the failure diagnosable.

**Step 5: Add one explicit recovery note to the plan execution**

For already-completed quests created before the escrow fix, either:

1. top up the client wallet after Task 2 and let direct debit succeed, or
2. restart the scenario from a fresh quest after Task 1 so the normal assign step creates a hold.

Do not hide legacy data inconsistency by silently minting money on confirm.

**Step 6: Re-run the focused tests**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_commission.py tests/test_quest_service.py -k "split_payment or confirm_quest" -q --tb=short`

Expected: escrow path and explicit no-hold path both pass.

**Step 7: Commit**

```bash
git add backend/app/services/quest_service.py backend/app/services/wallet_service.py backend/tests/test_quest_service.py backend/tests/test_commission.py
git commit -m "fix: harden confirm payout and escrow diagnostics"
```

### Task 4: Unify Refresh Handling to Stop Reload Races

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/context/AuthContext.tsx`
- Verify manually with: protected pages under `frontend/src/app/**`

**Step 1: Extract a shared refresh helper in `frontend/src/lib/api.ts`**

Create one shared function that owns refresh deduplication for the whole app.

```typescript
type RefreshResult = {
  access_token: string;
  user?: UserProfile;
} | null;

export async function refreshSession(): Promise<RefreshResult> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refreshResp = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!refreshResp.ok) return null;
      const refreshed = await refreshResp.json();
      setAccessToken(refreshed.access_token);
      return refreshed as RefreshResult;
    })().finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
}
```

**Step 2: Refactor `fetchApi()` to use `refreshSession()` instead of inline refresh logic**

Keep the existing retry-once behavior, but replace the embedded fetch to `/auth/refresh` with the shared helper.

**Step 3: Refactor `AuthContext` bootstrap to use the same helper**

Replace the direct `fetch(`${base}/auth/refresh`, ...)` call in `frontend/src/context/AuthContext.tsx` with `refreshSession()` imported from `@/lib/api`.

Expected shape:

```typescript
const refreshed = await refreshSession();
if (refreshed?.access_token && refreshed.user) {
  setToken(refreshed.access_token);
  setUser(refreshed.user);
  persistUser(refreshed.user);
} else {
  localStorage.removeItem(STORAGE_KEY_USER);
}
```

**Step 4: Make logout behavior depend on shared state, not duplicate heuristics**

Keep the current forced logout event, but make sure only the shared refresh helper decides refresh success/failure. The important rule is: one refresh request in flight, many consumers awaiting the same promise.

**Step 5: Run static verification**

Run: `cd frontend; npx tsc --noEmit`

Expected: no TypeScript errors.

Run: `cd frontend; npm run build`

Expected: production build passes.

**Step 6: Manual reload verification**

From a logged-in session, hard reload these pages directly in the browser:

1. `/profile`
2. `/profile/dashboard`
3. `/quests/create`
4. `/admin/users` for an admin account

Expected: no spurious `POST /api/v1/auth/refresh -> 401`, and UI remains authenticated after reload.

**Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/context/AuthContext.tsx
git commit -m "fix: dedupe refresh token rotation on reload"
```

### Task 5: Re-run the Full Flow Against a Fresh Quest

**Files:**
- No new code by default
- Use existing scripts and live browser flow

**Step 1: Apply all DB migrations before the run**

Run: `cd backend; .venv\Scripts\python.exe -m alembic upgrade head`

**Step 2: Start backend and frontend**

Run backend: `cd backend; .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`

Run frontend: `cd frontend; npm run dev`

**Step 3: Recreate the scenario from scratch**

Use a fresh client and freelancer, not the previously completed quest.

1. Admin tops up the client wallet through `/admin/users`.
2. Client creates a brand new quest.
3. Freelancer applies.
4. Client assigns freelancer.
5. Freelancer starts work.
6. Freelancer completes work.
7. Client confirms.

**Step 4: Verify the money path explicitly in the DB or API**

Expected:

1. On assign, a `transactions` row with `type='hold'` and `status='held'` exists.
2. On confirm, that hold becomes `completed`.
3. Freelancer receives `gross - fee`.
4. Platform wallet receives the fee.

**Step 5: Run backend regression suites**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_quest_service.py tests/test_admin_service.py tests/test_commission.py tests/test_endpoints.py -q --tb=short`

Expected: all touched areas pass.

**Step 6: Record outcome**

If the fresh flow passes but the legacy completed quest still fails without top-up, document that as legacy data cleanup, not as an open blocker in the primary flow.

**Step 7: Commit**

```bash
git add .
git commit -m "test: verify restored full quest flow"
```

## Notes for the Implementer

1. Do not “fix” quest creation by removing `platform_fee_percent` from inserts or models. That would reintroduce fee drift.
2. Do not auto-credit missing funds during confirm. If a quest has no hold and the client has no balance, that is either a legacy-data problem or an operational funding problem.
3. The reload bug is most likely a refresh-token rotation race, not a cookie flag issue on localhost. Keep cookie settings unchanged unless evidence says otherwise.

Plan complete and saved to `docs/plans/2026-03-10-full-quest-flow-blockers.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**