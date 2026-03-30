# Residual Auth And Guild Money Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Закрыть два оставшихся residual issue после повторного аудита: сделать production auth/session contract честным при недоступном Redis и выровнять guild money contract на фронтенде через единый normalization boundary.

**Architecture:** Для A-01 выбрать один production contract и не смешивать shared-state semantics с локальным fallback. Рекомендуемый путь: считать Redis обязательным для refresh-session в production, поднимать доменную ошибку из security helper и конвертировать её в контролируемый `503` на auth endpoints, оставив in-memory store только для dev/test. Для A-02 провести guild-domain через тот же frontend boundary, что уже используется для wallet/admin money: wire types остаются string-like только внутри `api.ts`, а UI-модели получают `MoneyAmount`.

**Tech Stack:** FastAPI, asyncpg, Redis, pytest, Next.js 14 App Router, TypeScript, React, npm, backend venv.

---

## Recommended Policy Decision

### A-01: Redis is required for refresh-session in production

Это лучший вариант для текущей архитектуры. Refresh token store участвует в login, register, refresh rotation и logout. In-memory fallback на одном процессе создаёт ложное ощущение degraded mode, но реально ломает cross-process semantics, revoke/rotate guarantees и поведение под несколькими pod/worker. Поэтому production должен либо иметь рабочий Redis, либо честно отдавать `503 Service Unavailable` на auth endpoints, завязанные на refresh-session storage.

### A-02: Guild money must follow the existing frontend money normalization rule

Это уже установленный контракт в проекте: backend сериализует `Decimal` как JSON string, а frontend нормализует их в `api.ts` до числовых UI-моделей. Guild-domain должен использовать тот же шаблон без исключений.

---

## Execution Rules

1. Не трогать закрытые audit topics вроде Alembic, readiness, admin TOTP и quest escrow, если новый тест прямо не покажет регрессию.
2. Для A-01 сначала зафиксировать contract тестами, потом править helper, потом endpoints.
3. Для A-02 сначала перевести типы на `MoneyAmount`, затем довести `api.ts` до зелёного `tsc`, и только потом править компонентную арифметику.
4. Не вводить новый frontend test framework ради этой задачи. Для frontend verification достаточно typecheck + production build, потому что нормализация реализуется в pure functions и типовом слое.
5. Один task = один commit. Не смешивать backend auth fix и frontend money normalization в одном diff.

---

## Batch 1: Make Refresh-Session Failure Honest In Production

Цель batch: убрать ложный in-memory fallback contract для production и превратить outage Redis из неявного runtime crash в контролируемый `503` только на затронутых auth endpoints.

### Task 1: Add failing unit tests for refresh-token storage policy

**Files:**
- Create: `backend/tests/test_security_refresh_store.py`
- Check: `backend/app/core/security.py`
- Check: `backend/app/core/redis_client.py`

**Step 1: Write the failing tests**

Add focused tests covering these cases:
- non-production or local mode: `create_refresh_token()` may use in-memory store when Redis is unavailable;
- production mode with Redis unavailable: refresh-token helper raises a dedicated service-availability error instead of silently claiming fallback;
- `verify_refresh_token()` and `revoke_refresh_token()` follow the same rule.

Suggested test cases:

```python
def test_create_refresh_token_uses_memory_store_outside_production(monkeypatch):
    ...

def test_create_refresh_token_raises_when_redis_required_in_production(monkeypatch):
    ...

def test_verify_refresh_token_raises_when_redis_required_in_production(monkeypatch):
    ...
```

**Step 2: Run the test file and verify it fails**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security_refresh_store.py -q --tb=short`

Expected: FAIL because current helper either raises raw `RuntimeError` or still implies fallback semantics.

**Step 3: Commit nothing yet**

This task only freezes the desired contract.

### Task 2: Introduce an explicit domain error for refresh-store unavailability

**Files:**
- Modify: `backend/app/core/security.py`
- Test: `backend/tests/test_security_refresh_store.py`

**Step 1: Implement the minimal boundary change**

Add a dedicated exception, for example:

```python
class RefreshTokenStoreUnavailableError(RuntimeError):
    pass
```

Then change the refresh-token helper path so that:
- dev/test or explicitly non-production mode may still use `_IN_MEMORY_REFRESH_STORE`;
- production Redis failure raises `RefreshTokenStoreUnavailableError`;
- warning logs about in-memory fallback are emitted only in the branch where fallback is truly allowed.

Do not leave comments that still claim production fallback.

**Step 2: Re-run the unit tests**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security_refresh_store.py -q --tb=short`

Expected: PASS.

**Step 3: Commit**

`git add backend/app/core/security.py backend/tests/test_security_refresh_store.py`

`git commit -m "fix: make refresh token storage contract explicit"`

### Task 3: Convert refresh-store failures into controlled 503 responses on auth endpoints

**Files:**
- Modify: `backend/app/api/v1/endpoints/auth.py`
- Test: `backend/tests/test_endpoints.py`
- Check: `backend/app/core/security.py`

**Step 1: Add failing endpoint tests**

Extend `backend/tests/test_endpoints.py` with focused cases for:
- `POST /api/v1/auth/register` returns `503` when refresh-token storage is unavailable;
- `POST /api/v1/auth/login` returns `503` when refresh-token storage is unavailable;
- `POST /api/v1/auth/refresh` returns `503` when refresh-token verification/rotation storage is unavailable;
- `POST /api/v1/auth/logout` returns `503` when revocation storage is unavailable and a refresh cookie is present.

Patch the auth module boundary rather than Redis itself in endpoint tests, for example by monkeypatching:

```python
auth.create_refresh_token = failing_stub
auth.verify_refresh_token = failing_stub
auth.revoke_refresh_token = failing_stub
```

**Step 2: Run the targeted endpoint slice and verify it fails**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_endpoints.py -q --tb=short -k "register or login or refresh or logout"`

Expected: FAIL because endpoints currently do not translate this failure mode into a stable `503` response.

**Step 3: Implement the minimal endpoint mapping**

In `auth.py`, catch `RefreshTokenStoreUnavailableError` around the refresh-token operations and raise:

```python
HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Authentication service temporarily unavailable",
)
```

Keep the scope tight:
- do not swallow DB errors;
- do not wrap unrelated validation/auth failures;
- use the same detail string across register/login/refresh/logout.

**Step 4: Re-run the endpoint slice**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_endpoints.py -q --tb=short -k "register or login or refresh or logout"`

Expected: PASS.

**Step 5: Commit**

`git add backend/app/api/v1/endpoints/auth.py backend/tests/test_endpoints.py`

`git commit -m "fix: return 503 when refresh session storage is unavailable"`

### Task 4: Verify no auth regression escaped the focused fix

**Files:**
- Check: `backend/tests/test_endpoints.py`
- Check: `backend/tests/test_admin_endpoints.py`

**Step 1: Run the focused auth-related backend slice**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security_refresh_store.py tests/test_endpoints.py -q --tb=short`

Expected: PASS.

**Step 2: Run the full backend suite only after the focused slice is green**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests -q --tb=short`

Expected: PASS.

**Step 3: Commit**

No new commit if Task 2 and Task 3 are already committed cleanly.

### Batch 1 exit criteria

- `security.py` no longer claims a production fallback it does not provide.
- Auth endpoints return controlled `503` instead of crashing or leaking raw infrastructure failure when Redis-backed refresh storage is unavailable.
- Dev/test can still use `_IN_MEMORY_REFRESH_STORE` if that behavior is intentionally preserved.

---

## Batch 2: Normalize Guild Money At The API Boundary

Цель batch: убрать последний mixed money contract в guild-domain и заставить UI работать только с normalized numeric money values.

### Task 5: Move guild UI models onto `MoneyAmount`

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Optional Check: `frontend/src/types/index.ts`

**Step 1: Make the UI types strict enough to expose the current drift**

Change guild-facing UI types so the following fields use `MoneyAmount` instead of `string`:
- `GuildCard.treasury_balance`
- `GuildActivityEntry.treasury_delta`
- `GuildSeasonalSet.reward_treasury_bonus`

Add raw wire types in `api.ts`, for example:

```ts
type GuildCardRaw = Omit<GuildCard, "treasury_balance"> & {
  treasury_balance: MoneyWire;
};

type GuildActivityEntryRaw = Omit<GuildActivityEntry, "treasury_delta"> & {
  treasury_delta: MoneyWire;
};
```

**Step 2: Run TypeScript and verify it fails**

Run: `Set-Location c:\QuestionWork\frontend; npx tsc --noEmit`

Expected: FAIL in `getTalentMarket`, `getGuildProfile`, and guild page code because the current API client still returns raw string money values.

**Step 3: Commit nothing yet**

This task intentionally creates the type pressure that will force the correct normalization work.

### Task 6: Add guild normalization functions in `api.ts`

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Step 1: Implement raw response types and normalizers**

Add the minimal set of raw types and pure normalizers:
- `GuildCardRaw`
- `GuildActivityEntryRaw`
- `GuildSeasonalSetRaw`
- `GuildDetailResponseRaw`
- `TalentMarketResponseRaw`
- `normalizeGuildCard()`
- `normalizeGuildActivityEntry()`
- `normalizeGuildSeasonalSet()`
- `normalizeGuildDetailResponse()`
- `normalizeTalentMarketResponse()`

Each money field must go through `toNumber()`.

**Step 2: Rewire endpoint functions to return normalized UI contracts**

Update:
- `getTalentMarket(...)`
- `getGuildProfile(...)`

So they fetch raw responses and return normalized ones, exactly like wallet/admin/template endpoints already do.

**Step 3: Re-run TypeScript**

Run: `Set-Location c:\QuestionWork\frontend; npx tsc --noEmit`

Expected: PASS or fail only in UI locations that still assume string-based guild money.

**Step 4: Commit**

`git add frontend/src/lib/api.ts`

`git commit -m "fix: normalize guild money responses at api boundary"`

### Task 7: Remove stringly money usage from guild page components

**Files:**
- Modify: `frontend/src/app/marketplace/guilds/[slug]/page.tsx`
- Check: `frontend/src/lib/api.ts`

**Step 1: Replace manual string coercion with numeric UI usage**

Update the guild page so it treats guild money fields as numbers everywhere:
- replace `Number(entry.treasury_delta)` checks with numeric comparisons;
- replace `Number(guild.treasury_balance)` calculations with direct numeric arithmetic;
- keep formatting responsibility in the component, but not parsing.

If needed, add tiny local helpers such as:

```ts
function formatMoney(value: number) {
  return value.toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}
```

Only add helpers if they remove repeated formatting/parsing logic.

**Step 2: Run TypeScript again**

Run: `Set-Location c:\QuestionWork\frontend; npx tsc --noEmit`

Expected: PASS.

**Step 3: Run the production build**

Run: `Set-Location c:\QuestionWork\frontend; npm run build`

Expected: PASS with no new guild money type errors.

**Step 4: Commit**

`git add frontend/src/app/marketplace/guilds/[slug]/page.tsx`

`git commit -m "fix: use normalized guild money values in marketplace ui"`

### Batch 2 exit criteria

- Guild money fields reach UI components only as `MoneyAmount`.
- `getTalentMarket()` and `getGuildProfile()` no longer leak Decimal wire strings into shared UI models.
- Guild page components do not parse money strings manually.
- `npx tsc --noEmit` and `npm run build` are green.

---

## Final Verification Sweep

Run these commands in order only after both batches are complete:

1. `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security_refresh_store.py tests/test_endpoints.py -q --tb=short`
2. `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests -q --tb=short`
3. `Set-Location c:\QuestionWork\frontend; npx tsc --noEmit`
4. `Set-Location c:\QuestionWork\frontend; npm run build`

Expected final state:
- backend auth/session failure mode is honest and controlled;
- frontend guild-domain money contract matches the rest of the app;
- no reopened backend regression from the auth change;
- no new frontend type/build regressions.

---

## Notes For The Implementer

1. Do not choose the degraded in-memory production mode unless product explicitly accepts single-process-only refresh semantics. That path is weaker and would require fresh ops documentation plus possibly readiness changes.
2. Keep the new backend error narrowly scoped to refresh-session storage unavailability. Avoid turning all Redis failures anywhere in the app into `503` from auth endpoints.
3. Do not leak raw `MoneyWire` outside `frontend/src/lib/api.ts` once the guild normalization work starts.

Plan complete and saved to `docs/plans/2026-03-11-residual-auth-guild-money-remediation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?