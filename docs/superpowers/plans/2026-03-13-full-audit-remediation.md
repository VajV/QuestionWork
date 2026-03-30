# Full Audit Remediation Plan (2026-03-13)

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all P1 and P2 issues from the 2026-03-13 full project audit, plus P3 hardening items. Zero regressions: 579 backend tests still pass, `tsc --noEmit` clean.

**Architecture:** Backend fixes span wallet service, quest service, admin service/endpoint, config, and users endpoint. Frontend fix is a type-contract adjustment in `api.ts`. Each chunk is independently deployable.

**Tech Stack:** Python 3.12 / FastAPI / asyncpg / Alembic / Pydantic v2, Next.js 14 / TypeScript

---

## Audit Findings — Status Overview

| ID | Sev | Title | Chunk |
|----|-----|-------|-------|
| P1-1 | P1 | No withdrawal idempotency key — duplicate withdrawals on retry | 1 |
| P1-2 | P1 | `cancel_quest()` dead-code logic — cannot cancel quest under revision | 1 |
| P2-2 | P2 | `AdminBroadcastNotificationRequest` allows empty `user_ids` | 2 |
| P2-3 | P2 | Admin force-complete requires escrow — no fallback path | 2 |
| P2-1 | P2 | Frontend money precision loss — `toNumber()` uses `Number()` | 3 |
| P2-4 | P2 | Frontend quest `budget` typed as `number` vs backend `Decimal` | 3 |
| P3-1 | P3 | `COOKIE_SECURE` defaults to `False` | 4 |
| P3-2 | P3 | f-string SQL column interpolation — safe but fragile pattern | 4 |

---

## Chunk 1 — P1: Withdrawal Idempotency + Quest Cancel Logic

### Task 1: Alembic migration — add `idempotency_key` to `transactions`

**Files:**
- Create: `backend/alembic/versions/a1b2c3d4e5f6_add_withdrawal_idempotency_key.py`
- Reference (read-only): `backend/app/services/wallet_service.py`

The `transactions` table needs a nullable `idempotency_key VARCHAR(64)` column with a partial UNIQUE index covering only `withdrawal` type rows, so legacy records are unaffected.

- [ ] **Step 0 (pre-step): Get the current Alembic head**

Run: `cd backend && .venv/Scripts/python.exe -m alembic heads`
Note the printed revision ID (e.g., `abc123def456`). You will paste it into `down_revision` in the migration file below.

- [ ] **Step 1: Create the migration file**

> **IMPORTANT:** In the snippet below, replace `<REPLACE_WITH_CURRENT_HEAD>` with the actual head ID from Step 0 before saving. Do NOT use the placeholder literally.

Create `backend/alembic/versions/a1b2c3d4e5f6_add_withdrawal_idempotency_key.py`:

```python
"""add withdrawal idempotency key

Revision ID: a1b2c3d4e5f6
Revises: <REPLACE_WITH_CURRENT_HEAD>   # ← paste the head ID from Step 0 here
Create Date: 2026-03-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '<REPLACE_WITH_CURRENT_HEAD>'   # ← paste the head ID from Step 0 here
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'transactions',
        sa.Column('idempotency_key', sa.String(64), nullable=True)
    )
    # Partial unique index: only enforces uniqueness among withdrawal rows
    op.create_index(
        'uq_transactions_withdrawal_idempotency_key',
        'transactions',
        ['idempotency_key'],
        unique=True,
        postgresql_where=sa.text("type = 'withdrawal' AND idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index('uq_transactions_withdrawal_idempotency_key', table_name='transactions')
    op.drop_column('transactions', 'idempotency_key')
```

> **Note:** Before creating the file, run `cd backend && .venv/Scripts/python.exe -m alembic heads` to get the current head revision and replace `<REPLACE_WITH_CURRENT_HEAD>`.

- [ ] **Step 2: Run the migration**

```
cd backend
.venv/Scripts/python.exe -m alembic upgrade head
```

Expected: migration applies cleanly with no errors.

---

### Task 2: Backend — `create_withdrawal()` idempotency logic

**Files:**
- Modify: `backend/app/services/wallet_service.py` (around line 575)
- Modify: `backend/app/api/v1/endpoints/wallet.py` (around line 29 and 98)

**wallet_service.py changes:**

- [ ] **Step 1: Add `idempotency_key` parameter to `create_withdrawal()`**

In `wallet_service.py`, update the function signature and add deduplication logic after the transaction guard:

```python
async def create_withdrawal(
    conn: asyncpg.Connection,
    user_id: str,
    amount,
    currency: str = "RUB",
    idempotency_key: Optional[str] = None,
) -> dict:
    """Request a withdrawal. Deducts from balance immediately with status=pending.

    Must be called inside an existing DB transaction.

    If idempotency_key is provided and a pending withdrawal with this key already
    exists for the user, returns the existing record without creating a duplicate.

    Raises:
        WithdrawalValidationError: If amount < MIN_WITHDRAWAL_AMOUNT.
        InsufficientFundsError: If balance is too low.
    """
    _assert_in_transaction(conn)

    # --- Idempotency check ---
    if idempotency_key:
        existing = await conn.fetchrow(
            """SELECT id, amount, currency, status
               FROM transactions
               WHERE user_id = $1 AND idempotency_key = $2 AND type = 'withdrawal'""",
            user_id,
            idempotency_key,
        )
        if existing:
            return {
                "transaction_id": existing["id"],
                "amount": _to_decimal(existing["amount"]),
                "currency": existing["currency"],
                "status": existing["status"],
                "new_balance": await get_balance(conn, user_id, currency),
                "idempotent": True,
            }
    # --- end idempotency check ---
```

Then in the `INSERT INTO transactions` statement, add the `idempotency_key` column:

```python
    tx_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO transactions (id, user_id, quest_id, amount, currency, type, status, idempotency_key, created_at)
        VALUES ($1, $2, NULL, $3, $4, $5, $6, $7, $8)
        """,
        tx_id,
        user_id,
        amount,
        currency,
        "withdrawal",
        "pending",
        idempotency_key,
        now,
    )
```

- [ ] **Step 2: Add `idempotency_key` field to `WithdrawRequest` in wallet.py**

In `backend/app/api/v1/endpoints/wallet.py`, update `WithdrawRequest`:

```python
class WithdrawRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, le=10_000_000, description="Amount to withdraw (must be > 0)")
    currency: str = Field(default="RUB", max_length=10)
    idempotency_key: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=64,
        description="Client-generated UUID to prevent duplicate withdrawals on retry",
    )
```

Add `from typing import Optional` to imports if not already present.

- [ ] **Step 3: Pass `idempotency_key` through in the endpoint**

In `wallet.py`, update the `withdraw()` call:

```python
            result = await wallet_service.create_withdrawal(
                conn,
                user_id=current_user.id,
                amount=body.amount,
                currency=body.currency,
                idempotency_key=body.idempotency_key,
            )
```

- [ ] **Step 4: Verify — run wallet tests**

```
cd backend && .venv/Scripts/python.exe -m pytest tests/test_wallet*.py -v --tb=short
```

Expected: all wallet tests pass.

---

### Task 3: Frontend — send `idempotency_key` on withdrawal

**Files:**
- Modify: `frontend/src/lib/api.ts` (near `withdrawFunds` function)

- [ ] **Step 1: Add `idempotency_key` to withdrawal request type and function**

Find the `WithdrawRequest` interface / withdrawal API function in `api.ts` and add the field. Also generate the key at call time using `crypto.randomUUID()`:

```typescript
// In the WithdrawRequest or WithdrawalPayload interface:
export interface WithdrawPayload {
  amount: string;         // MoneyWire — matches backend Decimal
  currency?: string;
  idempotency_key: string; // client-generated once per user action
}
```

In the function that sends `POST /wallet/withdraw`, generate the key once before creating the request and include it in the body. The caller is responsible for generating and storing the key per action, so the function should accept it as a parameter or the caller passes a pre-generated UUID:

```typescript
export async function withdrawFunds(amount: string, currency = "RUB"): Promise<WithdrawalResponse> {
  const idempotency_key = crypto.randomUUID();
  return fetchApi<WithdrawalResponse>(
    "/wallet/withdraw",
    {
      method: "POST",
      body: JSON.stringify({ amount, currency, idempotency_key }),
    },
    true,
  );
}
```

> **Note:** `crypto.randomUUID()` is available in all modern browsers and Next.js server environments. No additional import needed.

- [ ] **Step 2: Verify — TypeScript check**

```
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

---

### Task 4: Fix `cancel_quest()` dead-code logic bug

**Files:**
- Modify: `backend/app/services/quest_service.py` (around line 1122)

**Problem:** `revision_requested` appears in the rejection list at L1122, preventing cancellation of a quest under revision. This is dead code since the escrow refund branch at L1127 correctly handles the `revision_requested` state.

- [ ] **Step 1: Remove `revision_requested` from the rejection list**

In `quest_service.py`, find:

```python
        if quest["status"] in [QuestStatusEnum.completed.value, QuestStatusEnum.confirmed.value, QuestStatusEnum.cancelled.value, QuestStatusEnum.revision_requested.value]:
            raise ValueError(f"Cannot cancel quest with status: {quest['status']}")
```

Change to:

```python
        if quest["status"] in [
            QuestStatusEnum.completed.value,
            QuestStatusEnum.confirmed.value,
            QuestStatusEnum.cancelled.value,
        ]:
            raise ValueError(f"Cannot cancel quest with status: {quest['status']}")
```

The `was_in_progress` tuple below (which includes `revision_requested`) correctly triggers the escrow refund path.

- [ ] **Step 2: Write or update test for `cancel_quest` with revision_requested status**

**Pre-step:** Read `backend/tests/test_quest_service.py` lines 1–100 to understand the existing mock pattern. The file uses:
- `_make_conn()` — returns an `AsyncMock` with `is_in_transaction` returning `True` and `transaction()` returning a `_FakeTransaction` context manager
- `_make_user(role, user_id, grade)` — returns a `UserProfile`
- `_quest_row(quest_id, client_id, status, assigned_to, ...)` — returns a dict mimicking an asyncpg Record

Add the following test to `backend/tests/test_quest_service.py`:

```python
@pytest.mark.asyncio
async def test_cancel_quest_in_revision_requested_succeeds():
    """A quest under revision can be cancelled by the client, triggering escrow refund path."""
    conn = _make_conn()
    client = _make_user(role="client", user_id="user_client")
    quest = _quest_row(
        quest_id="quest_rev",
        client_id=client.id,
        status=QuestStatusEnum.revision_requested.value,
        assigned_to="freelancer-uuid",
    )

    # fetchrow: first call returns the quest, subsequent calls (e.g. escrow refund) return None
    conn.fetchrow.side_effect = [quest, None]
    conn.execute.return_value = None
    conn.fetchval.return_value = None
    conn.fetch.return_value = []

    # Should NOT raise ValueError — previously blocked by dead-code rejection list
    result = await quest_service.cancel_quest(conn, "quest_rev", client)
    assert result["status"] == "cancelled"
```

- [ ] **Step 3: Run quest tests**

```
cd backend && .venv/Scripts/python.exe -m pytest tests/test_quest*.py -v --tb=short
```

Expected: new test passes, no regressions.

---

## Chunk 2 — P2: Admin Broadcast Validation + Force-Complete Fallback

### Task 5: Add `min_length=1` to `AdminBroadcastNotificationRequest.user_ids`

**Files:**
- Modify: `backend/app/api/v1/endpoints/admin.py` (around line 150)

**Note:** The previous audit session found this was already partially discussed; confirm the current state of the field before editing.

- [ ] **Step 1: Add validation constraint**

In `admin.py`, change:

```python
class AdminBroadcastNotificationRequest(BaseModel):
    user_ids: List[str] = Field(default_factory=list)
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    event_type: str = Field(default="admin_broadcast")
```

To:

```python
class AdminBroadcastNotificationRequest(BaseModel):
    user_ids: List[str] = Field(..., min_length=1, description="At least one user ID is required")
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    event_type: str = Field(default="admin_broadcast")
```

- [ ] **Step 2: Add or update test**

In `backend/tests/test_admin_endpoints.py` or `test_admin_service.py`, verify that submitting `user_ids: []` returns HTTP 422:

```python
async def test_broadcast_notification_empty_user_ids_returns_422(async_client, admin_auth_headers):
    response = await async_client.post(
        "/api/v1/admin/broadcast-notification",
        json={"user_ids": [], "title": "Test", "message": "Test message"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 422
```

- [ ] **Step 3: Run admin tests**

```
cd backend && .venv/Scripts/python.exe -m pytest tests/test_admin*.py -v --tb=short
```

Expected: new test passes, no regressions.

---

### Task 6: Add `skip_escrow` fallback to `force_complete_quest()`

**Files:**
- Modify: `backend/app/services/admin_service.py` (around line 1213)
- Modify: `backend/app/api/v1/endpoints/admin.py` (the `AdminForceCompleteRequest` model and endpoint)

**Problem:** `force_complete_quest()` unconditionally raises `ValueError("Admin force-complete requires an active escrow hold")` if the hold is missing. Admins need a bypass for legacy quests or edge cases.

- [ ] **Step 1: Add `skip_escrow: bool` to the service function signature**

In `admin_service.py`, find:

```python
    if not hold_row:
        raise ValueError("Admin force-complete requires an active escrow hold")
```

Replace the block with:

```python
    if not hold_row:
        if not skip_escrow:
            raise ValueError(
                "Admin force-complete requires an active escrow hold. "
                "Pass skip_escrow=True to override (no payment will be made to freelancer)."
            )
        logger.warning(
            f"[AUDIT] Admin force-complete with no escrow hold: "
            f"quest={quest_id}, admin action, skip_escrow=True"
        )
        split_result = None  # no payment when escrow is missing
```

Update the function signature from:
```python
async def force_complete_quest(conn: asyncpg.Connection, quest_id: str, admin_id: str) -> dict:
```
To:
```python
async def force_complete_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    admin_id: str,
    skip_escrow: bool = False,
) -> dict:
```

- [ ] **Step 2: Add `skip_escrow` to the request Pydantic model and endpoint**

In `admin.py`, find the `AdminForceCompleteRequest` class (or similar) and add:

```python
class AdminForceCompleteRequest(BaseModel):
    skip_escrow: bool = Field(
        default=False,
        description="Allow force-completion even without an active escrow hold (no payout to freelancer)",
    )
```

In the endpoint handler, pass through:

```python
    result = await admin_service.force_complete_quest(
        conn, quest_id=quest_id, admin_id=current_user.id,
        skip_escrow=body.skip_escrow,
    )
```

- [ ] **Step 3: Add test for skip_escrow path**

In `test_admin_service.py`, add:

```python
@pytest.mark.asyncio
async def test_force_complete_quest_no_escrow_skip_escrow_true():
    """Admin can force-complete a quest with no escrow hold when skip_escrow=True."""
    conn = _make_conn()   # use the same _make_conn() helper as in test_quest_service.py
    quest_row = _make_quest_row(
        status="in_progress",
        assigned_to="freelancer-1",
        client_id="client-1",
    )
    # Simulate: quest exists, hold_row IS None (no escrow), freelancer row exists
    conn.fetchrow.side_effect = [
        quest_row,    # SELECT * FROM quests FOR UPDATE
        None,         # SELECT id FROM transactions ... type='hold' → no hold found
    ]
    conn.execute.return_value = None
    conn.fetchval.return_value = 0  # quests_completed count
    conn.fetch.return_value = []

    # Must NOT raise ValueError when skip_escrow=True
    result = await admin_service.force_complete_quest(
        conn, quest_id="quest-1", admin_id="admin-1", skip_escrow=True
    )
    assert result["status"] == "confirmed"


@pytest.mark.asyncio
async def test_force_complete_quest_no_escrow_raises_without_skip():
    """Admin force-complete raises ValueError when no escrow and skip_escrow=False."""
    conn = _make_conn()
    quest_row = _make_quest_row(status="in_progress", assigned_to="freelancer-1")
    conn.fetchrow.side_effect = [quest_row, None]  # quest found, hold row None
    conn.execute.return_value = None
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []

    with pytest.raises(ValueError, match="requires an active escrow hold"):
        await admin_service.force_complete_quest(conn, "quest-1", "admin-1", skip_escrow=False)
```

> **Note:** Adapt `_make_conn()` and `_make_quest_row()` calls to match the actual helper signatures in `test_admin_service.py`. Read the first 80 lines of that file before implementing.

- [ ] **Step 4: Run admin tests**

```
cd backend && .venv/Scripts/python.exe -m pytest tests/test_admin*.py -v --tb=short
```

Expected: new tests pass, no regressions.

---

## Chunk 3 — P2: Frontend Money Type Cleanup

### Task 7: Document precision constraint; type-guard `Quest.budget` and `QuestCreate.budget`

**Files:**
- Modify: `frontend/src/lib/api.ts` (lines ~152 `Quest`, ~189 `QuestCreate`, ~1685 `createQuest`, ~1888 `requestWithdrawal`, `toNumber` function)
- Modify: `frontend/src/types/index.ts` (if `Quest` or `QuestCreate` is duplicated there)

**Context:**
- `Quest.budget` is currently typed as `number` (line ~152). The backend sends `Decimal` as a string. `QuestRaw` wraps it as `MoneyWire` and `normalizeQuest()` converts via `toNumber()`.
- `QuestCreate.budget` is currently typed as `number` (line ~189). The `createQuest()` API function passes it through `JSON.stringify(questData)` — `JSON.stringify` serializes a JS number directly, which is fine for amounts < $1B.
- `requestWithdrawal(amount: number, ...)` at line ~1888 sends `amount` as a number; the backend accepts this since the Pydantic field `amount: Decimal` accepts numeric JSON.
- The simplest, least-breaking fix is to **document the precision constraint** and keep `Quest.budget` as `number` in the normalized form (consistent with current normalizeQuest usage throughout all 36 pages), while ensuring `toNumber()` has an explanatory JSDoc.

- [ ] **Step 0 (pre-step): Verify current `Quest.budget` type and usages**

Confirm the current definitions by reading:
- `frontend/src/lib/api.ts` lines 145–200 (Quest + QuestCreate interfaces)
- `frontend/src/lib/api.ts` lines 792–800 (QuestRaw type)
- `frontend/src/lib/api.ts` lines 1027–1033 (normalizeQuest function)

Run to find all `quest.budget` usages across the frontend:
```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: 0 errors (confirms no type changes are needed before we start).

- [ ] **Step 1: Add JSDoc to `Quest.budget` explaining the wire-format contract**

In `frontend/src/lib/api.ts`, in the `Quest` interface, annotate the `budget` field:

```typescript
export interface Quest {
  // ...
  /**
   * Quest budget in platform currency.
   * Normalized from backend Decimal (string) to JS number via normalizeQuest().
   * Safe for display/arithmetic for amounts ≤ $10,000,000 with ≤ 2 decimal places.
   */
  budget: number;
  // ...
}
```

In `QuestCreate`, annotate similarly:

```typescript
export interface QuestCreate {
  // ...
  /**
   * Budget in platform currency, sent as number.
   * Backend Decimal field accepts numeric JSON; precision safe for amounts ≤ $10,000,000.
   */
  budget: number;
  // ...
}
```

- [ ] **Step 2: Confirm `QuestRaw` and `normalizeQuest()` are unchanged**

No code change needed here — `QuestRaw` already correctly types `budget: MoneyWire` and `normalizeQuest()` calls `toNumber()`. Add a comment at the top of `normalizeQuest()`:

```typescript
/**
 * Converts wire-format Quest (budget as MoneyWire string) to normalized Quest (budget as number).
 * Safe: all platform budgets are ≤ $10,000,000 with ≤ 2 decimal places.
 */
function normalizeQuest(quest: QuestRaw): Quest {
  return {
    ...quest,
    budget: toNumber(quest.budget),
  };
}
```

- [ ] **Step 3: Fix all call sites that read `quest.budget` as a number**

Search for `quest.budget` usages across the frontend:

```
grep -rn "quest\.budget\|template\.budget" frontend/src --include="*.tsx" --include="*.ts"
```

For each result, verify:
- **Display sites** (e.g., `{quest.budget}` in JSX): acceptable as-is since `budget` is already `number` post-normalization
- **Arithmetic** (e.g., `quest.budget * 0.1`): acceptable as-is since precision is guaranteed for platform amounts
- **Sending to API** in `updateQuest()` — `budget` goes through `JSON.stringify` as a number, which the backend Decimal field accepts

If any untransformed `QuestRaw.budget` (the string) reaches a site expecting `number` without going through `normalizeQuest()`, fix by routing through `normalizeQuest()` first.

- [ ] **Step 4: Add inline comment to `toNumber()` documenting the precision constraint**

In `api.ts`, find the `toNumber` function and add:

```typescript
/**
 * Convert a MoneyWire string to a JS number for display/arithmetic.
 * Safe for amounts < 9,007,199,254,740,991 (Number.MAX_SAFE_INTEGER).
 * Platform guarantee: all money values ≤ $10,000,000 with at most 2 decimal places.
 * For amounts outside this range, use decimal.js.
 */
function toNumber(value: MoneyValueInput): number {
```

- [ ] **Step 5: Verify — TypeScript check and build**

```
cd frontend && npx tsc --noEmit
cd frontend && npm run build
```

Expected: 0 TypeScript errors, successful build.

---

## Chunk 4 — P3: Hardening

### Task 8: Default `COOKIE_SECURE=True` in config

**Files:**
- Modify: `backend/app/core/config.py` (line 44)
- Modify (or create): `backend/.env.local` (or document in `.env.example`)

- [ ] **Step 1: Flip the default**

In `config.py`, change:

```python
    COOKIE_SECURE: bool = False
```

To:

```python
    COOKIE_SECURE: bool = True
```

- [ ] **Step 2: Document the local dev override and add startup warning**

In `backend/.env.example` (or create it if absent), add:

```ini
# Local development only — disable HTTPS cookie requirement
COOKIE_SECURE=false
```

In `backend/.env` (your local dev env file), verify `COOKIE_SECURE=false` is set or add it now, BEFORE flipping the default in Step 1. Failure to do this will break refresh-token cookies in local dev.

Optionally, in `backend/app/core/config.py` add a startup warning to `validate_production_settings()` or at app init:

```python
import logging
_cfg_logger = logging.getLogger("app.core.config")

if settings.COOKIE_SECURE and settings.APP_ENV.lower() not in ("production", "prod"):
    pass  # expected: secure cookies on staging
if not settings.COOKIE_SECURE:
    _cfg_logger.warning("COOKIE_SECURE=False — refresh token cookies are not HTTPS-only. OK for local dev only.")
```

This makes it immediately visible in logs if `COOKIE_SECURE` is off in a non-local environment.

- [ ] **Step 3: Verify — run auth tests**

```
cd backend && .venv/Scripts/python.exe -m pytest tests/test_auth*.py -v --tb=short
```

Expected: all auth tests still pass (they mock the cookie behavior).

---

### Task 9: Add safety comments to f-string SQL in `users.py`

**Files:**
- Modify: `backend/app/api/v1/endpoints/users.py` (around line 321)

- [ ] **Step 1: Add invariant comment block**

In `users.py`, directly above the `order_column_map` dict and f-string query, add:

```python
    # SAFETY: f-string interpolation below is safe ONLY because:
    # 1. order_column comes from a whitelist map (see order_column_map) — never raw user input
    # 2. order_direction is validated to be exactly "ASC" or "DESC" — no injection vector
    # Do NOT copy this pattern without preserving both guards.
    order_column_map = {
```

- [ ] **Step 2: Verify — no functional change**

```
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --tb=short
```

Expected: 579 tests pass, 0 failed.

---

## Deployment Order

> **Critical:** Backend changes must be deployed before frontend changes that depend on them.

| Step | What to deploy | Why |
|------|---------------|-----|
| 1 | Chunk 1 backend (migration + wallet_service + quest_service) | Must exist before frontend sends `idempotency_key` |
| 2 | Chunk 2 backend (admin fixes) | Independent; can deploy in parallel with Chunk 1 |
| 3 | Chunk 3 frontend (type annotations) | Safe any time — no API contract change (budget stays `number` in normalized form) |
| 4 | Frontend `idempotency_key` (Task 3) | Deploy AFTER Chunk 1 backend is live; old backend silently ignores extra fields so it is forward-compatible |
| 5 | Chunk 4 (cookie default + SQL comment) | Backend-only; deploy anytime after Chunk 1 |

---

## Final Verification

After all chunks are complete:

- [ ] Run full backend test suite: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --tb=short` → 579+ passed, 0 failed
- [ ] Run TypeScript check: `cd frontend && npx tsc --noEmit` → 0 errors
- [ ] Run frontend build: `cd frontend && npm run build` → successful

---

## Production Readiness Checklist (post-fix)

| Requirement | Status |
|---|---|
| All tests pass | ✅ (verify after) |
| Zero TypeScript errors | ✅ (verify after) |
| Withdrawal idempotency | ✅ P1-1 fixed |
| Quest cancel logic correct | ✅ P1-2 fixed |
| Admin broadcast validation | ✅ P2-2 fixed |
| Force-complete escrow fallback | ✅ P2-3 fixed |
| Frontend money type contract | ✅ P2-1 + P2-4 fixed |
| `COOKIE_SECURE` defaults to True | ✅ P3-1 fixed |
| f-string SQL safety documented | ✅ P3-2 fixed |
