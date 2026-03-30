# Auth Session And Admin URL Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove browser-side auth refresh noise on public pages, make authenticated state survive hard reload and deep links in development, and stop admin collection endpoints from causing avoidable `307` redirects.

**Architecture:** Fix the root cause instead of patching symptoms. The auth failures are caused by frontend/backend host mismatch in development (`127.0.0.1` page talking to `localhost` API), which prevents the refresh cookie from reliably participating in session restore. The admin redirect issue is a frontend URL builder bug that appends trailing slashes to collection endpoints even though backend routes are canonical without them.

**Tech Stack:** Next.js 14 App Router, TypeScript, browser `fetch` with cookie-based refresh flow, FastAPI backend routes.

---

## File Map

- Modify: `frontend/src/lib/api.ts`
  Responsibility: API base URL resolution, refresh flow, shared endpoint builders, admin collection requests.
- Modify: `frontend/src/context/AuthContext.tsx`
  Responsibility: bootstrap session restore on app load and cleanup of stale local auth hints.
- Modify: `frontend/.env.local`
  Responsibility: local development API origin defaults.
- Modify: `frontend/next.config.mjs`
  Responsibility: CSP `connect-src` must still allow the resolved dev API origin.
- Optional verify-only reference: `backend/app/api/v1/endpoints/auth.py`
  Responsibility: refresh cookie path and rotation semantics; no code change expected unless verification proves frontend-only fix is insufficient.
- Optional verify-only reference: `backend/app/core/config.py`
  Responsibility: dev CORS/cookie defaults; no code change expected unless frontend host canonicalization still leaves mismatched origins.

## Chunk 1: Stabilize Dev Session Restore

### Task 1: Make frontend choose a development API origin that matches the current browser host

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/.env.local`
- Modify: `frontend/next.config.mjs`

- [ ] **Step 1: Add a focused base-URL resolver in `frontend/src/lib/api.ts`**

Implement a small helper near the top of the file, replacing the current `API_BASE_URL` constant:

```ts
function resolveApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();

  if (typeof window === "undefined") {
    return configured || "http://localhost:8000/api/v1";
  }

  const browserHost = window.location.hostname;
  const browserProtocol = window.location.protocol;

  if (!configured) {
    return `${browserProtocol}//${browserHost}:8000/api/v1`;
  }

  try {
    const url = new URL(configured);
    const isLoopbackHost = url.hostname === "localhost" || url.hostname === "127.0.0.1";
    const isBrowserLoopback = browserHost === "localhost" || browserHost === "127.0.0.1";

    if (isLoopbackHost && isBrowserLoopback) {
      url.hostname = browserHost;
      return url.toString().replace(/\/$/, "");
    }

    return configured.replace(/\/$/, "");
  } catch {
    return configured.replace(/\/$/, "");
  }
}

const API_BASE_URL = resolveApiBaseUrl();
```

- [ ] **Step 2: Keep local env aligned with canonical development behavior**

In `frontend/.env.local`, either remove the hardcoded host override entirely or change it to the same canonical host used for day-to-day dev. Preferred minimal option:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
```

Reason: the runtime resolver will still normalize loopback hostnames to the active browser host, but the checked-in local default should stop biasing the app toward `localhost` when the team has already standardized on `127.0.0.1:3000` for recovery and Playwright validation.

- [ ] **Step 3: Keep CSP aligned with the same dev origin logic**

Update `frontend/next.config.mjs` so `connect-src` in development allows both loopback variants without relying on whichever one happens to be baked into `NEXT_PUBLIC_API_URL`:

```js
const devLoopbackOrigins = ["http://localhost:8000", "http://127.0.0.1:8000"];

if (isDev) {
  connectSrc.push(...devLoopbackOrigins, "ws:", "wss:");
}
```

Make sure duplicates are removed if you normalize the array.

- [ ] **Step 4: Verify the login response now sets/rotates a usable refresh cookie for the same host family**

Run in browser after `npm run dev` and backend is up:

1. Open the app on `http://127.0.0.1:3000`
2. Log in as `novice_dev / password123`
3. Hard refresh on `/profile`
4. Open a deep link like `/quests/<existing-id>`

Expected:
- User remains authenticated after reload.
- No guest header flash that persists.
- `POST /api/v1/auth/refresh` returns `200`, not `401`, when restore is needed.

### Task 2: Make session bootstrap tolerant but not noisy when restore is impossible

**Files:**
- Modify: `frontend/src/context/AuthContext.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add an explicit bootstrap gate for stale local user hints**

Refactor the auth-init path so it only treats local storage as a restore candidate after validating the stored shape and after a refresh attempt has a realistic chance of succeeding. Keep the UX rule simple:

```ts
const storedUser = readValidatedStoredUser();
if (!storedUser) {
  setLoading(false);
  return;
}

const data = await refreshSession();
if (data?.access_token && data.user) {
  // restore session
} else {
  clearStoredAuthHint();
}
```

Do not emit `console.error` for the expected "no refresh session available" case.

- [ ] **Step 2: Ensure `refreshSession()` is a silent capability probe, not an error amplifier**

Keep `refreshSession()` returning `null` on expected unauthenticated outcomes (`401`, abort, missing cookie). Do not let the call path turn these outcomes into browser-visible errors or thrown exceptions during bootstrap.

- [ ] **Step 3: Verify public pages stay clean**

Browser verification:

1. Open `/auth/login` in a fresh unauthenticated tab.
2. Open `/auth/register` in a fresh unauthenticated tab.
3. Open `/quests/<id>` after logging out.

Expected:
- No console error from `/api/v1/auth/refresh`.
- Public pages remain usable.
- If no session exists, app behaves as anonymous without noisy retries.

## Chunk 2: Remove Admin Redirect Churn

### Task 3: Stop appending a trailing slash to collection endpoints with query strings

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Replace the current collection endpoint builder**

Current code forces `/path/?query=...`, which backend redirects to `/path?query=...`. Replace it with:

```ts
function buildCollectionEndpoint(path: string, params: URLSearchParams): string {
  const normalizedPath = path.endsWith("/") ? path.slice(0, -1) : path;
  const query = params.toString();
  return query ? `${normalizedPath}?${query}` : normalizedPath;
}
```

- [ ] **Step 2: Verify all admin collection callers still use the shared helper**

Confirm these call sites still route through the helper and need no extra edits:

```ts
adminGetUsers()
adminGetTransactions()
adminGetPendingWithdrawals()
adminGetLogs()
```

- [ ] **Step 3: Verify network traces are clean**

Browser verification on admin pages:

1. Log in as admin.
2. Visit `/admin/users`.
3. Visit `/admin/withdrawals`.
4. Visit `/admin/logs`.

Expected:
- Requests go directly to `/api/v1/admin/users?page=...`
- Requests go directly to `/api/v1/admin/withdrawals/pending?page=...`
- Requests go directly to `/api/v1/admin/logs?page=...`
- No extra `307 Temporary Redirect` entries for those collection endpoints.

## Chunk 3: Final Verification

### Task 4: Run project-level verification for the touched surface area

**Files:**
- Modify: `docs/reports/playwright-browser-audit-2026-03-11.md` only if re-audit findings materially change

- [ ] **Step 1: Run static verification**

Run:

```bash
cd frontend
npx tsc --noEmit
npm run build
```

Expected:
- TypeScript passes.
- Next production build passes.

- [ ] **Step 2: Run browser verification for the three reported problems**

Re-run the same live checks:

1. Public auth pages
2. Login followed by hard reload on authenticated routes
3. Direct quest deep link after login
4. Admin users/withdrawals/logs network capture

Expected:
- No public-page `401 /auth/refresh` console noise.
- Auth survives reload/deep link.
- No admin `307` redirect churn.

- [ ] **Step 3: Update the audit report with fixed/not-fixed status**

If everything is green, append a short recheck section to the audit file noting:

- issue 1 fixed
- issue 2 fixed
- issue 3 fixed

If anything remains, record the exact failing route, console error, and network evidence instead of marking it resolved.

---

Plan complete and saved to `docs/superpowers/plans/2026-03-11-auth-session-and-admin-url-fixes.md`. Ready to execute.