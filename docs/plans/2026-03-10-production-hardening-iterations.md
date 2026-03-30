# QuestionWork Production Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the confirmed audit findings in small, low-risk iterations that can be shipped and verified independently.

**Architecture:** The work is split by risk domain rather than by file tree. First lock down security invariants, then normalize cross-layer API contracts, then remove schema drift and validation debt, then finish reliability, performance, and coverage. Each iteration is designed to be small enough for a single focused coding session with clear verification gates.

**Tech Stack:** FastAPI, asyncpg, PostgreSQL, Alembic, Next.js 14 App Router, TypeScript, pytest, npm build.

---

## Execution Rules

1. Work in order. Do not start the next iteration until the current one is green.
2. Prefer TDD for backend and contract fixes.
3. Keep commits scoped to one iteration.
4. After each iteration, run only the smallest relevant verification set first, then the broader regression checks.
5. If one iteration reveals new drift outside its scope, capture it separately and do not expand the batch unless it blocks completion.

---

## Iteration 1: Security Invariants

**Scope:** P1-01, P1-04

**Why first:** These changes are small, high-value, and mostly backend-only. They reduce production auth risk without touching UI contracts.

**Files likely involved:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_security.py`
- Test: `backend/tests/test_security_hardening.py`
- Test: `backend/tests/test_endpoints.py`

**Deliverables:**
- Access JWT includes and validates `iss` and `aud`
- Admin TOTP replay protection fails closed in production when Redis is unavailable
- Dev/test fallback remains allowed for local work

**Task breakdown:**

### Task 1.1: Add JWT issuer and audience claims

**Steps:**
1. Add explicit token claims in `create_access_token()`.
2. Enforce issuer and audience validation in `decode_access_token()`.
3. Add focused tests for valid token, missing audience, wrong issuer.
4. Run focused auth/security tests.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security.py tests/test_endpoints.py -q --tb=short`

### Task 1.2: Make admin TOTP replay protection fail closed in production

**Steps:**
1. Change admin TOTP verification path so Redis is mandatory in production.
2. Keep current in-memory fallback only for development and test.
3. Add tests covering production behavior and non-production fallback.
4. Run focused hardening tests.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security_hardening.py tests/test_endpoints.py -q --tb=short`

**Commit:**
- `git add backend/app/core/security.py backend/app/api/deps.py backend/app/core/config.py backend/tests/test_security.py backend/tests/test_security_hardening.py backend/tests/test_endpoints.py`
- `git commit -m "fix: harden jwt claims and admin totp replay protection"`

---

## Iteration 2: API Contract Hardening

**Scope:** P1-02, P1-03

**Why second:** This is the highest-value cross-layer fix after auth. It removes silent financial/UI bugs and stabilizes admin observability.

**Files likely involved:**
- Modify: `backend/app/main.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/app/admin/logs/page.tsx`
- Modify: `frontend/src/app/admin/dashboard/page.tsx`
- Modify: `frontend/src/app/admin/quests/page.tsx`
- Modify: `frontend/src/components/rpg/WalletPanel.tsx`
- Modify: `frontend/src/components/rpg/WalletBadge.tsx`

**Deliverables:**
- Money fields use one explicit contract end-to-end
- Frontend normalizes Decimal-backed fields centrally
- Admin log payload formatter handles object, string, and null safely

**Task breakdown:**

### Task 2.1: Define one money contract for frontend

**Steps:**
1. Decide on canonical frontend representation for Decimal-backed backend values.
2. Add central parsing or adapters in `frontend/src/lib/api.ts`.
3. Update TS interfaces in `api.ts` and `types/index.ts` to match reality.
4. Adjust wallet/admin/quest consumers to avoid implicit coercion.
5. Run frontend build.

**Verify:**
- `Set-Location c:/QuestionWork/frontend; npm run build`

### Task 2.2: Fix admin logs payload typing and rendering

**Steps:**
1. Update admin log payload types from `string | null` to a safe union.
2. Replace the current formatter in `admin/logs/page.tsx` with a serializer that handles objects and strings separately.
3. Verify CSV export still works with object payloads.
4. Run frontend build.

**Verify:**
- `Set-Location c:/QuestionWork/frontend; npm run build`

**Commit:**
- `git add frontend/src/lib/api.ts frontend/src/types/index.ts frontend/src/app/admin/logs/page.tsx frontend/src/app/admin/dashboard/page.tsx frontend/src/app/admin/quests/page.tsx frontend/src/components/rpg/WalletPanel.tsx frontend/src/components/rpg/WalletBadge.tsx`
- `git commit -m "fix: normalize decimal api contracts and admin log payloads"`

---

## Iteration 3: Schema Truth And Data Hygiene

**Scope:** P1-05, P2-03

**Why third:** These are low-effort consistency fixes that prevent future migration regressions and garbage admin input.

**Files likely involved:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/api/v1/endpoints/admin.py`
- Modify: `backend/app/services/admin_service.py`
- Test: `backend/tests/test_admin_endpoints.py`
- Test: `backend/tests/test_admin_service.py`

**Deliverables:**
- ORM matches applied migrations for `email` and `avg_rating`
- Admin user update validates `skills` as bounded string list

**Task breakdown:**

### Task 3.1: Remove ORM/Alembic schema drift

**Steps:**
1. Align `UserORM.email` and `UserORM.avg_rating` with the applied migrations.
2. Confirm no accidental metadata drift remains for these columns.
3. Run backend tests touching admin/review areas.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_admin_service.py tests/test_endpoints.py -q --tb=short`

### Task 3.2: Validate admin-updated `skills`

**Steps:**
1. Change request schema in admin endpoints to typed `list[str]` with limits.
2. Ensure service layer stores only validated values.
3. Add negative tests for non-string items, too many items, oversized items.
4. Run focused admin tests.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_admin_endpoints.py tests/test_admin_service.py -q --tb=short`

**Commit:**
- `git add backend/app/db/models.py backend/app/api/v1/endpoints/admin.py backend/app/services/admin_service.py backend/tests/test_admin_endpoints.py backend/tests/test_admin_service.py`
- `git commit -m "fix: align orm schema and validate admin skills payloads"`

---

## Iteration 4: Reliability And Query Performance

**Scope:** P2-01, P2-02

**Why fourth:** These changes are operationally useful but should land after the higher-risk auth and contract work.

**Files likely involved:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/db/models.py`
- Create: new Alembic migration under `backend/alembic/versions/`
- Test: `backend/tests/test_endpoints.py`
- Optional benchmark or manual explain notes

**Deliverables:**
- `/health` becomes a pure liveness endpoint
- `/ready` remains the diagnostic readiness endpoint
- `quests.skills` gets a GIN index for JSONB filter usage

**Task breakdown:**

### Task 4.1: Separate liveness and readiness semantics

**Steps:**
1. Simplify `/health` to an unconditional liveness response.
2. Keep DB/Redis status only in `/ready`.
3. Update tests that assert health behavior.
4. Run endpoint tests.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_endpoints.py tests/test_security_hardening.py -q --tb=short`

### Task 4.2: Add GIN index for quest skill filtering

**Steps:**
1. Add migration for GIN index on `quests.skills`.
2. Mirror the index in ORM metadata if this repo uses models for future autogenerate reference.
3. Add a short verification note or test proving migration applies cleanly.
4. Run backend tests and migration path check.

**Verify:**
- `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_endpoints.py tests/test_quest_service.py -q --tb=short`

**Commit:**
- `git add backend/app/main.py backend/app/db/models.py backend/alembic/versions backend/tests/test_endpoints.py backend/tests/test_quest_service.py`
- `git commit -m "fix: separate health semantics and index quest skills"`

---

## Iteration 5: Coverage, UX, And Warning Cleanup

**Scope:** P2-04, P3-01, P3-02

**Why last:** This batch is larger and safer once behavior and contracts are already stable.

**Files likely involved:**
- Modify: `backend/tests/test_admin_service.py`
- Modify: `backend/tests/test_review_service.py` or create if needed
- Modify: `backend/tests/test_phase2_classes.py`
- Modify: `backend/tests/test_template_service.py`
- Modify: `backend/tests/test_integration.py`
- Modify: `backend/tests/test_endpoints.py`
- Modify: `frontend/src/app/auth/register/page.tsx`

**Deliverables:**
- Better coverage on class, review, admin, template flows
- Frontend password rules mirror backend
- Deprecation warnings removed from test suite

**Task breakdown:**

### Task 5.1: Raise backend coverage in the riskiest service areas

**Steps:**
1. Add missing tests for `review_service` edge cases.
2. Add missing tests for class perk/ability/reset flows.
3. Add missing tests for admin destructive and financial flows.
4. Add missing tests for template lifecycle.
5. Run full backend pytest and inspect coverage deltas.

**Verify:**
- `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest -q --tb=short`

### Task 5.2: Mirror password complexity in the frontend register flow

**Steps:**
1. Reuse backend password requirements in the register UI.
2. Show actionable validation messages before submit.
3. Run frontend build.

**Verify:**
- `Set-Location c:/QuestionWork/frontend; npm run build`

### Task 5.3: Remove remaining test deprecation warnings

**Steps:**
1. Replace legacy event loop access in `test_integration.py`.
2. Move deprecated per-request cookie usage to client-level cookie setup in endpoint tests.
3. Re-run full backend test suite and confirm warnings are gone or reduced to unrelated third-party noise.

**Verify:**
- `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest -q --tb=short`

**Commit:**
- `git add backend/tests frontend/src/app/auth/register/page.tsx`
- `git commit -m "test: raise coverage and remove validation drift"`

---

## Suggested Session Commands

Use these prompts verbatim to execute one iteration at a time.

### Command A: Iteration 1

`Выполни Iteration 1 из docs/plans/2026-03-10-production-hardening-iterations.md: исправь JWT claims и fail-closed поведение admin TOTP replay protection, сначала добавь/обнови тесты, потом минимальную реализацию, затем прогони релевантные backend тесты.`

### Command B: Iteration 2

`Выполни Iteration 2 из docs/plans/2026-03-10-production-hardening-iterations.md: нормализуй Decimal/money API contract между backend и frontend и исправь runtime typing/rendering в admin logs. После изменений обязательно прогони frontend build.`

### Command C: Iteration 3

`Выполни Iteration 3 из docs/plans/2026-03-10-production-hardening-iterations.md: синхронизируй ORM с Alembic schema truth и добавь строгую валидацию admin skills payload. Нужны focused backend tests.`

### Command D: Iteration 4

`Выполни Iteration 4 из docs/plans/2026-03-10-production-hardening-iterations.md: раздели /health и /ready по semantics и добавь GIN index для quests.skills. После этого прогони backend tests и проверь миграции.`

### Command E: Iteration 5

`Выполни Iteration 5 из docs/plans/2026-03-10-production-hardening-iterations.md: подними coverage для class/review/admin/template service, выровняй frontend password validation с backend и убери оставшиеся pytest deprecation warnings.`

---

## Smallest Useful First Slice

Если нужен самый безопасный старт без большого diff, начни так:

1. Iteration 1 полностью
2. Из Iteration 2 только admin logs typing bug
3. Из Iteration 3 только ORM/Alembic drift

Это даст быстрый выигрыш по security, observability и schema correctness с минимальным объёмом фронтовых изменений.

---

## Release Gates By Iteration

**После Iteration 1:** backend auth hardening green

**После Iteration 2:** frontend build green, admin pages stable, wallet/admin number handling explicit

**После Iteration 3:** schema metadata drift removed

**После Iteration 4:** readiness semantics clear, quest filter scalable

**После Iteration 5:** regression confidence materially improved
