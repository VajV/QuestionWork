# Runtime Route Map, Auth Refresh, And E2E Remediation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the remaining live-audit failures by making the backend startup path deterministic on local runtime, reducing auth refresh churn under rapid protected-route navigation, and updating the E2E lifecycle harness to match the current escrow contract.

**Architecture:** This remediation spans three related but separable surfaces. First, lock down the backend launch path and add runtime verification so the server on `127.0.0.1:8000` cannot silently serve an outdated router set versus source. Second, harden frontend auth refresh orchestration so protected-page bootstrap does not fan out overlapping refresh requests and trip rate limits during fast navigation. Third, bring the existing lifecycle harness in line with the current wallet-hold rule by funding the client before assignment and asserting the escrow-aware path explicitly.

**Tech Stack:** FastAPI, asyncpg, Uvicorn, PowerShell dev scripts, Next.js 14 App Router, TypeScript, browser fetch auth refresh flow, pytest, headless Playwright verification.

---

## File Map

- Modify: `backend/scripts/run.ps1`
  Responsibility: canonical local backend launcher.
- Modify: `scripts/start-all.ps1`
  Responsibility: unified dev startup path; must start the same backend command as the canonical launcher and verify the live route map, not just `/health`.
- Modify: `scripts/check-status.ps1`
  Responsibility: status diagnostics should detect route-map drift, not only port/listener health.
- Modify: `frontend/src/lib/api.ts`
  Responsibility: shared fetch wrapper, refresh flow, request deduplication, protected endpoint bootstrap behavior.
- Modify: `frontend/src/context/AuthContext.tsx`
  Responsibility: session restore bootstrap and stale-auth cleanup semantics.
- Modify: `scripts/test_e2e.py`
  Responsibility: full quest lifecycle harness used during live verification.
- Modify: `docs/reports/playwright-browser-audit-2026-03-11.md`
  Responsibility: append recheck evidence only after fixes are verified live.
- Reference only: `backend/app/api/v1/api.py`
  Responsibility: authoritative router inclusion list.
- Reference only: `backend/app/api/v1/endpoints/analytics.py`
  Responsibility: defines `/analytics/events` and `/analytics/funnel-kpis`.
- Reference only: `backend/app/api/v1/endpoints/notifications.py`
  Responsibility: defines `/notifications/preferences`.

---

## Chunk 1: Make Local Backend Runtime Deterministic

### Task 1: Replace “port is listening” checks with route-map verification

**Files:**
- Modify: `backend/scripts/run.ps1`
- Modify: `scripts/start-all.ps1`
- Modify: `scripts/check-status.ps1`
- Reference: `backend/app/api/v1/api.py`

- [ ] **Step 1: Add a reusable expected-route list to the backend launcher**

In `backend/scripts/run.ps1`, define a small PowerShell array before starting Uvicorn:

```powershell
$ExpectedApiPaths = @(
    "/api/v1/analytics/events",
    "/api/v1/analytics/funnel-kpis",
    "/api/v1/notifications/preferences"
)
```

This list must represent the exact audit-failing paths that exist in source and must be present in runtime OpenAPI.

- [ ] **Step 2: Start Uvicorn through the venv Python executable explicitly**

Replace the raw shell call:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

with:

```powershell
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Reason: make the runtime path deterministic and avoid relying on whichever `uvicorn` binary happens to be first on `PATH`.

- [ ] **Step 3: Add a post-start OpenAPI verification helper to `backend/scripts/run.ps1`**

Create a focused helper in PowerShell:

```powershell
function Test-ExpectedApiPaths {
    param(
        [string]$OpenApiUrl,
        [string[]]$ExpectedPaths
    )

    $doc = Invoke-RestMethod -Uri $OpenApiUrl -TimeoutSec 5
    $missing = @()

    foreach ($path in $ExpectedPaths) {
        if (-not ($doc.paths.PSObject.Properties.Name -contains $path)) {
            $missing += $path
        }
    }

    return $missing
}
```

After the backend responds on `/health`, call it against `http://127.0.0.1:8000/openapi.json`. If any route is missing, print a red error that includes the path list and exit non-zero instead of leaving a stale backend running unnoticed.

- [ ] **Step 4: Make `scripts/start-all.ps1` use the canonical backend launcher instead of an inline command string**

Replace the embedded backend command that currently shells out to plain `uvicorn` with a call to the canonical script:

```powershell
$backendRunScript = Join-Path $BACKEND_DIR "scripts\run.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", $backendRunScript -WindowStyle Normal
```

Do not duplicate the backend startup command in two places anymore.

- [ ] **Step 5: Extend `scripts/start-all.ps1` readiness check to fail on route drift**

After the existing backend health wait loop, fetch `http://127.0.0.1:8000/openapi.json` and assert all three expected paths are present. If not, print a warning that the backend listener is up but the runtime route map is stale, and do not mark backend startup as healthy.

- [ ] **Step 6: Extend `scripts/check-status.ps1` with an API-surface check**

Add a status line that distinguishes these states:

```text
[OK] Backend port 8000 listening
[OK] Backend /health reachable
[OK] Runtime route map contains analytics + notification preference endpoints
```

or:

```text
[WARN] Backend is listening but runtime route map is missing:
- /api/v1/analytics/events
- /api/v1/analytics/funnel-kpis
- /api/v1/notifications/preferences
```

- [ ] **Step 7: Verify the launcher catches stale runtime**

Run:

```powershell
cd C:\QuestionWork\backend
.\scripts\run.ps1
```

Expected:
- backend starts via `.venv\Scripts\python.exe -m uvicorn`
- `/health` returns `200`
- `/openapi.json` contains the three expected paths
- script does not silently succeed if the runtime route map is incomplete

### Task 2: Reconfirm that runtime now matches source after a clean restart

**Files:**
- Reference: `backend/app/api/v1/api.py`
- Reference: `backend/app/api/v1/endpoints/analytics.py`
- Reference: `backend/app/api/v1/endpoints/notifications.py`

- [ ] **Step 1: Kill any existing listener on `8000`**

Run:

```powershell
$connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($connections) {
    $connections | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
}
```

Expected: port `8000` is free.

- [ ] **Step 2: Start backend through the canonical launcher only**

Run:

```powershell
cd C:\QuestionWork\backend
.\scripts\run.ps1
```

Expected: exactly one healthy backend instance is running.

- [ ] **Step 3: Verify runtime endpoints directly**

Run:

```powershell
$openapi = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/openapi.json'
@(
  '/api/v1/analytics/events',
  '/api/v1/analytics/funnel-kpis',
  '/api/v1/notifications/preferences'
) | ForEach-Object {
  if ($openapi.paths.PSObject.Properties.Name -contains $_) { "FOUND $_" } else { "MISSING $_" }
}
```

Expected: all three lines are `FOUND ...`.

- [ ] **Step 4: Verify live HTTP responses, not only OpenAPI**

Run authenticated probes for admin and freelancer:

```powershell
$admin = (Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body '{"username":"admin","password":"Admin123!"}').access_token
$freelancer = (Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body '{"username":"novice_dev","password":"password123"}').access_token
Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/analytics/funnel-kpis' -Headers @{ Authorization = "Bearer $admin" } -UseBasicParsing
Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/notifications/preferences' -Headers @{ Authorization = "Bearer $freelancer" } -UseBasicParsing
```

Expected: both return `200`, not `404`.

---

## Chunk 2: Remove Auth Refresh Churn Under Rapid Protected Navigation

### Task 3: Serialize refresh attempts so bootstrap cannot fan out duplicate `/auth/refresh` calls

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/context/AuthContext.tsx`

- [ ] **Step 1: Add a shared in-flight refresh promise in `frontend/src/lib/api.ts`**

Near the auth-token helpers, add:

```ts
let refreshInFlight: Promise<TokenResponse | null> | null = null;
```

This becomes the single authority for concurrent refresh callers.

- [ ] **Step 2: Refactor `refreshSession()` to reuse the same promise**

Wrap the current fetch call:

```ts
export async function refreshSession(): Promise<TokenResponse | null> {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  refreshInFlight = (async () => {
    try {
      const refreshResp = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });

      if (refreshResp.status === 401) {
        return null;
      }

      if (!refreshResp.ok) {
        throw new ApiError("Session refresh failed", refreshResp.status);
      }

      return (await refreshResp.json()) as TokenResponse;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        return null;
      }
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}
```

Do not allow parallel callers to start parallel refresh HTTP requests.

- [ ] **Step 3: Make the fetch wrapper avoid nested refresh storms**

When a protected request sees `401`, it may trigger a refresh. Add a guard so requests already calling `/auth/refresh` do not recurse, and so protected callers reuse the same `refreshInFlight` instead of launching another refresh attempt.

- [ ] **Step 4: Keep bootstrap tolerant to expected unauthenticated outcomes**

In `frontend/src/context/AuthContext.tsx`, preserve the existing “silent null restore” behavior for the no-session case. The bootstrap flow should:

```ts
const storedUser = readStoredUserHint();
if (!storedUser) {
  setLoading(false);
  return;
}

const data = await refreshSession();
if (!data?.access_token || !data.user) {
  clearStoredUser();
  setLoading(false);
  return;
}
```

Do not log expected `401` refresh misses as hard errors.

- [ ] **Step 5: Add a focused frontend verification pass for churn**

Run a headless Playwright probe that logs in once, then rapidly loads:

```text
/profile
/messages
/notifications
/profile/class
/profile
```

Expected:
- session remains authenticated
- `POST /api/v1/auth/refresh` is absent or appears at most once per restore cycle
- no `429` on `/api/v1/auth/refresh`
- `/notifications` no longer bounces to login during a warm authenticated session

### Task 4: Update frontend audit expectations for runtime-only 404 noise

**Files:**
- Modify: `frontend/src/lib/api.ts` only if needed for request-path normalization

- [ ] **Step 1: Recheck the two observed 404 callers after backend runtime is fixed**

Revisit these frontend call sites:

```ts
adminGetFunnelKPIs()
getNotificationPreferences()
trackAnalyticsEvent()
```

Only change code if the requests are still malformed after the backend restart verification. If runtime restart alone fixes the 404s, leave the call sites untouched.

- [ ] **Step 2: Verify there is no remaining client-side path bug**

Manual or Playwright check:

1. log in as admin and open `/admin/growth`
2. log in as freelancer and open `/notifications`
3. load a normal app page and confirm analytics event ingestion no longer 404s in network logs

Expected: all three requests return non-404 responses.

---

## Chunk 3: Update E2E Harness For Escrow-Aware Assignment

### Task 5: Make `scripts/test_e2e.py` reflect the current money flow contract

**Files:**
- Modify: `scripts/test_e2e.py`
- Reference: `backend/app/services/quest_service.py`
- Reference: `backend/app/api/v1/endpoints/admin.py`

- [ ] **Step 1: Add admin login to the test harness before lifecycle steps**

Near the existing login/setup section, add:

```python
r, s = api("POST", "/auth/login", {
    "username": "admin",
    "password": "Admin123!"
})
test("Login admin", s == 200 and "access_token" in r, f"status={s}")
admin_token = r.get("access_token", "")
```

- [ ] **Step 2: Fund the client wallet before assignment**

Immediately after client registration, add:

```python
r, s = api(
    "POST",
    f"/admin/users/{client_id}/adjust-wallet",
    {
        "amount": 5000,
        "currency": "RUB",
        "reason": "E2E escrow funding"
    },
    admin_token,
)
test("Fund client wallet", s == 200, f"status={s}")
```

- [ ] **Step 3: Assert wallet balance before publish/assign path**

Add an explicit balance check:

```python
r, s = api("GET", "/wallet/balance", None, client_token)
balances = r.get("balances", []) if isinstance(r, dict) else []
rub_balance = next((b.get("balance") for b in balances if b.get("currency") == "RUB"), None)
test("Client wallet funded", s == 200 and rub_balance is not None and float(rub_balance) >= 3000, f"status={s}, balance={rub_balance}")
```

- [ ] **Step 4: Keep assign/start/confirm assertions unchanged except for new escrow precondition**

Do not weaken the lifecycle assertions. The goal is still a full successful flow; only the missing precondition changes.

- [ ] **Step 5: Run the updated harness and confirm the old false negative is gone**

Run:

```powershell
cd C:\QuestionWork
c:/QuestionWork/backend/.venv/Scripts/python.exe scripts/test_e2e.py
```

Expected: assign no longer fails because of missing client funds; the full flow passes end-to-end.

---

## Chunk 4: Final Live Recheck

### Task 6: Repeat the audit and update the report with evidence

**Files:**
- Modify: `docs/reports/playwright-browser-audit-2026-03-11.md`

- [ ] **Step 1: Run static and targeted backend verification**

Run:

```powershell
cd C:\QuestionWork\frontend
node_modules\.bin\tsc --noEmit

cd C:\QuestionWork\backend
& "C:\QuestionWork\backend\.venv\Scripts\python.exe" -m pytest "C:\QuestionWork\backend\tests\test_analytics.py" "C:\QuestionWork\backend\tests\test_lifecycle.py" -v --tb=short --override-ini="addopts="
```

Expected:
- TypeScript passes
- targeted backend tests pass

- [ ] **Step 2: Re-run the live role audit with headless Playwright**

Repeat the same live checks used in the audit:

1. admin login and `/admin/growth`
2. freelancer login and `/notifications`
3. client login and rapid protected-page navigation
4. full lifecycle harness

Expected:
- no `404` on funnel KPIs
- no `404` on notification preferences
- no `404` on analytics ingestion
- no `429` on `/auth/refresh` during rapid protected navigation
- no unexpected bounce from `/notifications` to `/auth/login`
- lifecycle harness passes with wallet funding built in

- [ ] **Step 3: Append a recheck section to the audit report**

Update `docs/reports/playwright-browser-audit-2026-03-11.md` with:

- the exact commands used for the recheck
- final status of the stale-route issue
- final status of the refresh churn issue
- final status of the lifecycle harness drift

Do not mark any item fixed without including the live verification evidence.

---

Plan complete and saved to `docs/superpowers/plans/2026-03-13-runtime-route-refresh-and-e2e-remediation.md`. Ready to execute.