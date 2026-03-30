# Admin TOTP, Readiness, And Body Limit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the three confirmed post-hardening gaps: missing frontend admin TOTP support, readiness semantics drift relative to production Redis requirements, and the request-body limit bypass for streamed or chunked requests.

**Architecture:** Handle this as three isolated risk domains. First restore production admin operability by completing the frontend half of the TOTP contract. Next align readiness with actual production dependencies so orchestration does not route traffic to partially broken pods. Last harden oversized request handling with a streaming-safe enforcement path and explicit infrastructure guidance.

**Tech Stack:** FastAPI, asyncpg, Redis, Next.js 14 App Router, TypeScript, React Context, pytest, npm build.

---

## Execution Rules

1. Work in order. Do not start the next iteration until the current one is green.
2. Prefer TDD where practical: failing test first, then minimal implementation.
3. Keep each commit scoped to one iteration.
4. Run the smallest relevant verification set first, then broader regression checks.
5. Do not expand scope into unrelated admin polish or generic auth cleanup unless it blocks the current iteration.

---

## Iteration 1: Restore Admin TOTP End-To-End Contract

**Scope:** Frontend support for backend-required `X-TOTP-Token` admin requests.

**Why first:** This is the only confirmed production-blocker. Production config already requires admin TOTP, and the backend contract is active now.

**Files likely involved:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/context/AuthContext.tsx`
- Modify: `frontend/src/app/auth/login/page.tsx`
- Modify: `frontend/src/app/admin/layout.tsx`
- Modify: `frontend/src/types/index.ts`
- Create or modify: admin-auth helper module under `frontend/src/lib/`
- Test: `backend/tests/test_security_hardening.py`
- Test: frontend behavior verified by build and manual admin flow

**Deliverables:**
- Frontend can collect/store an admin TOTP code for the current session
- Admin API calls include `X-TOTP-Token` when needed
- Expired/missing TOTP state is surfaced clearly and recoverably in UI

### Task 1.1: Freeze the backend contract in tests/documented behavior

**Steps:**
1. Re-read and confirm the backend behavior in `require_admin()` and admin TOTP endpoints.
2. Add or tighten focused backend tests for:
   - admin request without `X-TOTP-Token` returns 403 when TOTP is required
   - admin request with valid token passes
   - repeated token is rejected by replay protection
3. Run the focused backend security tests.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest c:/QuestionWork/backend/tests/test_security_hardening.py -q --tb=short`

### Task 1.2: Add client-side admin TOTP session state

**Steps:**
1. Add a small frontend helper or context for current admin TOTP token state.
2. Keep the token in memory only for the session; do not persist it in localStorage.
3. Expose helpers to set, clear, and read the TOTP token.
4. Ensure logout clears this state.

**Verify:**
- `Set-Location c:/QuestionWork/frontend; npm run build`

### Task 1.3: Attach `X-TOTP-Token` to admin requests only

**Steps:**
1. Extend `fetchApi()` so admin routes can opt into adding the TOTP header.
2. Avoid sending the header globally to non-admin routes.
3. Keep the existing Bearer-token and refresh-cookie behavior unchanged.
4. Verify existing admin API helpers use the new path.

**Verify:**
- `Set-Location c:/QuestionWork/frontend; npm run build`

### Task 1.4: Add minimal admin UX for TOTP-required flows

**Steps:**
1. Add a lightweight UI path for entering or refreshing the TOTP code before using admin screens.
2. Ensure the admin layout handles missing TOTP state explicitly instead of failing silently through repeated 403s.
3. Show actionable error handling when the token is missing, invalid, or expired.
4. Run frontend build.

**Verify:**
- `Set-Location c:/QuestionWork/frontend; npm run build`

### Task 1.5: Regression verification

**Steps:**
1. Run frontend production build.
2. Run the full backend suite to ensure TOTP/auth changes did not regress security paths.
3. Manually verify: admin login, TOTP setup/enable, dashboard load, one admin mutation.

**Verify:**
- `Set-Location c:/QuestionWork/frontend; npm run build`
- `cmd /c "set SECRET_KEY=dev-secret-key-questionwork & c:\QuestionWork\backend\.venv\Scripts\python.exe -m pytest c:\QuestionWork\backend\tests -q --tb=short"`

**Commit:**
- `git add frontend/src/lib/api.ts frontend/src/context/AuthContext.tsx frontend/src/app/auth/login/page.tsx frontend/src/app/admin/layout.tsx frontend/src/types/index.ts backend/tests/test_security_hardening.py`
- `git commit -m "fix: complete admin totp flow on frontend"`

---

## Iteration 2: Align Readiness With Production Security Dependencies

**Scope:** Make `/ready` reflect the actual minimum production dependency set.

**Why second:** Once admin TOTP is operational, readiness must stop reporting healthy when the production security contract is already broken.

**Files likely involved:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_endpoints.py`
- Test: `backend/tests/test_security_hardening.py`
- Optional doc note: `README.md` or ops docs if readiness semantics are documented

**Deliverables:**
- `/health` stays a pure liveness probe
- `/ready` fails when Redis is required for production auth invariants and Redis is unavailable
- readiness semantics are explicit and test-covered

### Task 2.1: Define readiness rules per environment

**Steps:**
1. Document the intended rule in code comments/tests:
   - development/test: DB required, Redis may be degraded
   - production with admin TOTP required: DB and Redis are both required
2. Add or update tests to encode this behavior.
3. Run focused endpoint tests.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest c:/QuestionWork/backend/tests/test_endpoints.py -q --tb=short`

### Task 2.2: Implement conditional readiness failure on Redis dependency

**Steps:**
1. Update `/ready` to compute readiness from the real dependency contract instead of DB-only status.
2. Preserve the current detailed checks payload.
3. Ensure the response still distinguishes degraded vs required-failure cases clearly.
4. Re-run focused tests.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest c:/QuestionWork/backend/tests/test_endpoints.py c:/QuestionWork/backend/tests/test_security_hardening.py -q --tb=short`

### Task 2.3: Regression verification

**Steps:**
1. Run the full backend test suite.
2. If needed, manually hit `/health` and `/ready` with Redis available and unavailable.

**Verify:**
- `cmd /c "set SECRET_KEY=dev-secret-key-questionwork & c:\QuestionWork\backend\.venv\Scripts\python.exe -m pytest c:\QuestionWork\backend\tests -q --tb=short"`

**Commit:**
- `git add backend/app/main.py backend/app/core/config.py backend/tests/test_endpoints.py backend/tests/test_security_hardening.py`
- `git commit -m "fix: align readiness with production redis requirements"`

---

## Iteration 3: Close The Streamed Request Body Limit Bypass

**Scope:** Enforce request-size limits even when `Content-Length` is missing or misleading.

**Why third:** This is a real hardening gap, but it is lower risk than the admin production blocker and can be implemented independently.

**Files likely involved:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_audit_p0p1_fixes.py`
- Modify or create: dedicated middleware tests under `backend/tests/`
- Optional doc update: reverse-proxy limits in `README.md` or deployment docs

**Deliverables:**
- Oversized streamed/chunked requests are rejected server-side
- `Content-Length` validation remains fast-path optimization, not the only guard
- deployment docs explicitly recommend proxy-level body-size limits as defense in depth

### Task 3.1: Add failing tests for no-Content-Length oversized requests

**Steps:**
1. Add test coverage for:
   - malformed `Content-Length`
   - valid oversized `Content-Length`
   - oversized body without `Content-Length`
   - streamed/chunked request exceeding limit mid-read
2. Confirm at least the new no-`Content-Length` case fails before implementation.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest c:/QuestionWork/backend/tests/test_audit_p0p1_fixes.py -q --tb=short`

### Task 3.2: Implement streaming-safe body-size enforcement

**Steps:**
1. Replace the header-only guard with middleware that counts actual body bytes read.
2. Preserve current 400 behavior for malformed `Content-Length` if still desired.
3. Return 413 as soon as the configured limit is exceeded.
4. Ensure this does not break standard JSON request handling or CORS/error wrapping.

**Verify:**
- `c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest c:/QuestionWork/backend/tests/test_audit_p0p1_fixes.py c:/QuestionWork/backend/tests/test_endpoints.py -q --tb=short`

### Task 3.3: Add infrastructure defense-in-depth note

**Steps:**
1. Add a short deployment note requiring proxy-level body-size limits as a second line of defense.
2. Mention nginx/Caddy/container ingress equivalents if docs already contain deployment guidance.

**Verify:**
- Docs-only review

### Task 3.4: Regression verification

**Steps:**
1. Run the full backend test suite.
2. Optionally run one manual oversized request against a dev server if convenient.

**Verify:**
- `cmd /c "set SECRET_KEY=dev-secret-key-questionwork & c:\QuestionWork\backend\.venv\Scripts\python.exe -m pytest c:\QuestionWork\backend\tests -q --tb=short"`

**Commit:**
- `git add backend/app/main.py backend/tests/test_audit_p0p1_fixes.py backend/tests/test_endpoints.py README.md`
- `git commit -m "fix: enforce body limits for streamed requests"`

---

## Iteration 4: Cleanup And Contract Tightening

**Scope:** Residual typing/contract cleanup discovered during the re-audit.

**Why last:** This is not the root production breakage, but it is worth cleaning after the core risks are closed.

**Files likely involved:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: admin pages/components consuming normalized money values

**Deliverables:**
- Frontend shared types reflect normalized money values consistently
- No misleading `number` declarations remain where backend contract is still stringly before normalization

### Task 4.1: Normalize shared admin money types

**Steps:**
1. Audit `frontend/src/types/index.ts` against the actual normalized output of `frontend/src/lib/api.ts`.
2. Remove any stale contract drift for wallets/admin totals/adjust-wallet responses.
3. Run frontend build.

**Verify:**
- `Set-Location c:/QuestionWork/frontend; npm run build`

**Commit:**
- `git add frontend/src/types/index.ts frontend/src/lib/api.ts`
- `git commit -m "refactor: align frontend money types with normalized api responses"`

---

## Suggested Session Commands

Use these prompts verbatim to execute one iteration at a time.

### Command A: Iteration 1

`Выполни Iteration 1 из docs/plans/2026-03-10-admin-totp-readiness-body-limit.md: закрой production-blocker по admin TOTP end-to-end. Сначала зафиксируй backend contract тестами, потом добавь frontend session-state и X-TOTP-Token для admin API, затем минимальный UI для ввода/обновления TOTP и прогони frontend build + relevant backend tests.`

### Command B: Iteration 2

`Выполни Iteration 2 из docs/plans/2026-03-10-admin-totp-readiness-body-limit.md: выровняй /ready с production dependency contract, чтобы readiness падал при недоступном Redis там, где production admin auth без него не работает. Нужны focused backend tests и затем полный backend pytest.`

### Command C: Iteration 3

`Выполни Iteration 3 из docs/plans/2026-03-10-admin-totp-readiness-body-limit.md: закрой обход лимита размера тела запроса для streamed/chunked запросов без Content-Length. Сначала добавь падающие тесты, потом минимальную streaming-safe middleware реализацию, затем backend regression tests.`

### Command D: Iteration 4

`Выполни Iteration 4 из docs/plans/2026-03-10-admin-totp-readiness-body-limit.md: дочисти frontend money/type contract drift после основных фиксов, не меняя backend semantics. После изменений обязательно прогони frontend build.`

---

## Smallest Useful First Slice

Если нужен самый безопасный старт с минимальным diff:

1. Iteration 1 полностью
2. Из Iteration 2 только readiness rule + tests
3. Из Iteration 3 только failing tests и минимальный middleware fix

Это сначала восстановит production-admin operability, потом поправит orchestration semantics, и только затем закроет request-size bypass.

---

## Release Gates By Iteration

**После Iteration 1:** admin frontend работает с enforced TOTP без 403 loop

**После Iteration 2:** readiness соответствует production security contract

**После Iteration 3:** oversized streamed requests reliably rejected server-side

**После Iteration 4:** frontend contract drift around normalized money values removed