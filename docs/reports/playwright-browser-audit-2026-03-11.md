# Playwright Browser Audit - 2026-03-11

## Scope

- Frontend: http://127.0.0.1:3000
- Backend: http://127.0.0.1:8000
- Roles covered: admin, client, freelancer
- Method: live browser checks with UI navigation, console capture, and network capture

## Verified Working Flows

### Admin

- Login with `admin / Admin123!`
- Dashboard opens successfully
- Users page opens successfully
- Quests page opens successfully
- Withdrawals page opens successfully
- Audit logs page opens successfully and renders table/filter/export controls

### Client

- Registration of a new client account succeeds
- Redirect to profile after registration succeeds
- Quest creation form opens successfully
- Quest creation succeeds for `Audit client quest 20260311`
- Redirect to created quest detail page succeeds

### Freelancer

- Login with `novice_dev / password123` succeeds
- Profile opens successfully
- Quest board opens successfully
- Newly created client quest is visible on the board
- Application modal opens successfully
- Application submission succeeds

## Findings

### Medium - Public pages trigger failed auth refresh and emit console error

- Evidence: browser console consistently reports `Failed to load resource: the server responded with a status of 401 (Unauthorized) @ http://localhost:8000/api/v1/auth/refresh`
- Reproduced on public auth pages during normal navigation
- Impact: unauthenticated users see noisy error logging in the browser; this can hide real issues during debugging and indicates the frontend attempts session refresh even when no valid refresh session exists

### Medium - Hard reload / direct deep link loses authenticated state

- Reproduction:
  1. Log in as freelancer
  2. Open a quest via direct URL load
  3. Page falls back to guest header with `Войти / Примкнуть`
- Impact: authenticated navigation works through in-app links, but direct URL entry or hard refresh can drop the active session, which is a real UX/auth stability problem for bookmarked pages and reload recovery
- Related evidence: after direct navigation, network captured `POST /api/v1/auth/refresh => 401 Unauthorized`

### Low - Admin API calls incur avoidable `307 Temporary Redirect` churn

- Reproduced on admin routes such as:
  - `/api/v1/admin/users/?page=1&page_size=20`
  - `/api/v1/admin/withdrawals/pending/?page=1&page_size=20`
  - `/api/v1/admin/logs/?page=1&page_size=30`
- Observed behavior: frontend first requests URL variants with trailing slash before query string, backend returns `307`, then the browser retries the canonical URL without the extra slash and receives `200`
- Impact: does not break admin flows, but adds unnecessary requests, extra latency, and noisy network traces

## Notes

- No blocking browser-side crash was found in the tested admin, client, and freelancer flows
- No failed quest creation or failed quest application was observed in the verified scenarios
- Admin UI sections rendered successfully despite the redirect churn noted above

## Recheck After Fixes

### Status Of Original Findings

- Issue 1 (`401 /auth/refresh` noise on public pages): fixed
- Issue 2 (session lost after hard reload / deep link): fixed functionally
- Issue 3 (admin collection endpoints causing extra `307`): fixed

### Evidence

- Public `/auth/login` recheck produced no console errors and no `401` refresh request.
- Deep-link recheck on `/quests/746aa56a-256f-46e4-9efd-39f4c352e2f9` showed `POST /api/v1/auth/refresh => 200 OK`, after which the authenticated header and user actions were restored.
- Admin collection requests now hit canonical URLs directly:
  - `/api/v1/admin/withdrawals/pending?page=1&page_size=20 => 200 OK`
  - `/api/v1/admin/logs?page=1&page_size=30 => 200 OK`
  - no extra `307 Temporary Redirect` entries were observed for those rechecked admin endpoints.

### Residual Notes

- On direct load of a public deep-link page, the first snapshot can still briefly render the anonymous header before client bootstrap restores the session. The original functional failure is resolved, but a small unauthenticated first-paint flash may remain as a UX nuance.
- Outside the original three issues, the recheck still observed trailing-slash redirect churn on `notifications` API requests. This is separate from the admin collection bug that was fixed.

## Live Recheck On Target Runtime - 2026-03-13

### Runtime Recovery Status

- Target backend on `http://127.0.0.1:8000` was rechecked after clearing a stale local listener condition on port `8000`.
- Runtime OpenAPI on `8000` now includes the previously missing paths:
  - `/api/v1/analytics/events`
  - `/api/v1/analytics/funnel-kpis`
  - `/api/v1/notifications/preferences`
- Local database drift was corrected by applying the missing Alembic head, after which:
  - `GET /api/v1/notifications/preferences => 200`
  - `GET /api/v1/analytics/funnel-kpis => 200`
- Analytics KPI aggregation also required a code fix in `backend/app/services/analytics_service.py`: the query now reads from `applications` instead of the non-existent `quest_applications` table used by the broken local runtime.

### Final UI Recheck

- Method: headless live browser recheck against the fixed frontend on `http://127.0.0.1:3000` and backend on `http://127.0.0.1:8000`
- Admin flow:
  - `admin / Admin123!` login succeeded
  - `/admin/growth` opened successfully
  - growth funnel table rendered with KPI rows including `Applications submitted`, `Hires`, and `Confirmed completions`
- Freelancer flow:
  - `novice_dev / password123` login succeeded
  - `/notifications` opened successfully
  - notifications hub rendered without auth bounce and showed the unified relay UI

### Final Evidence

- No `404`, `429`, or `500` responses were captured during the final admin/freelancer UI recheck.
- No browser console errors were captured during the final admin/freelancer UI recheck.
- No redirect back to `/auth/login` occurred while opening `/admin/growth` or `/notifications` in the final run.

### Conclusion

- The previously blocked live recheck on the target runtime is now green.
- Audit report updated only after the repaired `:8000` runtime and final UI verification both passed.