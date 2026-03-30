# TestSprite Bug Fix Plan — ✅ COMPLETED 2026-03-26

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Remove confirmed frontend E2E failures found by TestSprite, separate real product bugs from runtime noise, and lock fixes with focused regression coverage.

## Final Status (2026-03-26)
All 8 tasks completed. Code fixes verified working locally and via TestSprite:
- **5 TCs passing** (TC039, TC040, TC041, TC043, TC047) — up from 0
- **4 TCs blocked by tunnel** (TC023, TC027, TC028, TC029) — code fixes verified locally
- **1 TC test-design limit** (TC030) — page loads OK, no compose button by design
- **1 TC data gap** (TC045) — no full event to test failure case
- Full report: `frontend/testsprite_tests/testsprite-mcp-test-report.md`

**Architecture:** The plan treats failures in three buckets: product bugs, data/setup gaps, and runtime instability. Investigation starts at the failing boundary for each bucket, then applies the smallest root-cause fix and adds regression coverage at the API and UI layers.

**Tech Stack:** Next.js 14 App Router, TypeScript, FastAPI, asyncpg, PostgreSQL, TestSprite E2E, pytest, frontend TypeScript checks.

---

## Scope Split

### Product bugs to fix first
- Messaging page returns internal server error.
- Profile/dashboard navigation is inconsistent with expected route.
- Admin user search flow returns no usable records for detail navigation.

### Data and seed gaps to fix second
- Events list is empty, blocking event details, join, and leaderboard scenarios.
- Quest discovery scenarios depend on missing fixture coverage for specific filters.

### Runtime and infrastructure noise to isolate separately
- Intermittent `Failed to fetch`, `ERR_EMPTY_RESPONSE`, and timeout failures during login and authenticated flows.
- TestSprite tunnel hangs on some long-running batches.

---

## Relevant Code Areas

- Frontend messaging: `frontend/src/app/messages/page.tsx`
- Frontend auth redirect: `frontend/src/context/AuthContext.tsx`
- Frontend login page: `frontend/src/app/auth/login/page.tsx`
- Frontend profile routes: `frontend/src/app/profile/page.tsx`, `frontend/src/app/profile/dashboard/page.tsx`
- Frontend events: `frontend/src/app/events/page.tsx`, `frontend/src/app/events/[id]/page.tsx`
- Frontend admin users: `frontend/src/app/admin/users/page.tsx`, `frontend/src/app/admin/users/[id]/page.tsx`
- Shared frontend API client: `frontend/src/lib/api.ts`
- Backend messages: `backend/app/api/v1/endpoints/messages.py`, `backend/app/services/message_service.py`
- Backend events: `backend/app/api/v1/endpoints/events.py`, `backend/app/services/event_service.py`
- Backend admin users: `backend/app/api/v1/endpoints/admin.py`, `backend/app/services/admin_service.py`

---

## Task 1: Stabilize Triage Inputs

**Outcome:** Separate actionable product bugs from false negatives before touching feature code.

- [ ] Re-run only the environment-sensitive login cases and record whether failures reproduce outside TestSprite tunnel.
- [ ] Compare failing TestSprite cases against local frontend and backend logs captured during the same window.
- [ ] Mark each failing case as one of: product bug, data gap, test expectation mismatch, or runtime noise.
- [ ] Freeze a short canonical bug list for implementation work so feature fixes are not mixed with transport noise.

**Verification:** A single table exists with each failed TC mapped to one owner bucket.

---

## Task 2: Fix Messaging Internal Server Error

**Files:**
- Modify: `frontend/src/app/messages/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `backend/app/api/v1/endpoints/messages.py`
- Modify: `backend/app/services/message_service.py`
- Test: backend message endpoint tests and frontend smoke for `/messages`

**Likely root-cause questions:**
- Does `/api/v1/messages/dialogs` fail for valid authenticated users?
- Does the frontend call the wrong route or assume data shape that backend does not return?
- Is the page expecting quest-linked dialogs when the backend requires pre-existing quest membership?

- [ ] Reproduce `/messages` failure with a valid authenticated user and capture the exact backend exception.
- [ ] Verify request path and response shape used by `getMessageDialogs()` and page loader.
- [ ] Fix the failing boundary only: route mismatch, auth assumption, null handling, or DB query precondition.
- [ ] Add backend regression coverage for dialogs list and message send preconditions.
- [ ] Add frontend loading, empty, and error-state assertions for `/messages`.

**Verification:** `/messages` loads without 500 for seeded valid users and TC026-class flows reach UI validation state.

---

## Task 3: Fix Profile Dashboard Routing Contract

**Files:**
- Modify: `frontend/src/context/AuthContext.tsx`
- Modify: `frontend/src/app/auth/login/page.tsx`
- Modify: `frontend/src/app/profile/page.tsx`
- Modify: `frontend/src/app/profile/dashboard/page.tsx`

**Likely root-cause questions:**
- Should successful non-admin login land on `/profile` or `/profile/dashboard`?
- Does `profile/dashboard` redirect unconditionally to another page, breaking the test contract?
- Is the app using one canonical dashboard route but exposing another link target in UI?

- [ ] Confirm the intended canonical post-login route for freelancer users.
- [ ] Align login redirect, protected-route redirect, and profile navigation to the same route contract.
- [ ] Remove any redirect loop or fallback that sends users to `/quests` unexpectedly.
- [ ] Add one focused regression test for successful login redirect and one for direct navigation to `/profile/dashboard`.

**Verification:** Authenticated freelancer lands consistently on the chosen profile dashboard route and direct navigation does not bounce to unrelated pages.

---

## Task 4: Repair Admin Users Search and Detail Flow

**Files:**
- Modify: `frontend/src/app/admin/users/page.tsx`
- Modify: `frontend/src/app/admin/users/[id]/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `backend/app/api/v1/endpoints/admin.py`
- Modify: `backend/app/services/admin_service.py`

**Likely root-cause questions:**
- Is the frontend applying a search term that no current fixture can match?
- Does backend search filter only exact fields while UI expects broader matching?
- Is pagination or role filtering dropping all results?

- [ ] Reproduce admin users search with the exact TestSprite filter and inspect returned payload.
- [ ] Decide whether the fix belongs in data seeding, backend search semantics, or test expectation.
- [ ] If search semantics are too strict, implement the minimal broadening needed for username/email display-name lookup.
- [ ] Ensure the detail page can open from a visible row returned by the default seeded dataset.
- [ ] Add backend tests for admin user search and a frontend regression for opening a user record from filtered results.

**Verification:** Admin search returns at least one deterministic seeded record for the supported query and detail navigation succeeds.

---

## Task 5: Restore Events E2E Coverage with Deterministic Data

**Files:**
- Modify: `frontend/src/app/events/page.tsx`
- Modify: `frontend/src/app/events/[id]/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `backend/app/api/v1/endpoints/events.py`
- Modify: `backend/app/services/event_service.py`
- Modify: seed or fixture setup responsible for event presence

**Likely root-cause questions:**
- Are events missing because none are seeded, all are inactive, or date filters exclude them?
- Does the frontend correctly render empty state while tests expect seeded demo content?
- Are join and leaderboard scenarios blocked by valid business rules or by missing fixtures?

- [ ] Inspect how active events are selected and why `/events` is empty in the seeded runtime.
- [ ] Decide whether to seed one deterministic active event or relax environment-specific filters for demo data.
- [ ] Ensure one event supports details, join action, and leaderboard rendering in non-admin flows.
- [ ] Keep empty-state UI intact, but make seeded environments include at least one active event for E2E.
- [ ] Add backend tests for active event listing and frontend regression for event details page rendering.

**Verification:** `/events` shows at least one deterministic event in test runtime, details page opens, and leaderboard/join flows are reachable.

---

## Task 6: Reconcile Quest Discovery Test Expectations

**Files:**
- Modify: `frontend/src/app/quests/page.tsx` or related marketplace page
- Modify: `frontend/src/lib/api.ts`
- Modify: backend quest list/filter service if filter semantics are wrong
- Modify: seed or fixture data for discoverable quests

- [ ] Re-check failed quest-discovery cases against current seed data and supported filters.
- [ ] Decide per failure whether the application is missing a feature or the test expects non-existent fixture coverage.
- [ ] For `Load more`, confirm whether pagination exists. If not, close the gap by updating product expectation or implementing actual pagination, but do not fake the control.
- [ ] Ensure at least one quest matches the documented filter combinations used in smoke/E2E.

**Verification:** Discovery smoke cases are deterministic and no longer depend on accidental dataset contents.

---

## Task 7: Isolate Runtime Instability from Feature Bugs

**Files:**
- Modify as needed in runtime startup config, auth flow, or HTTP client retry/timeout handling only after root cause is identified

- [ ] Correlate `Failed to fetch` and `ERR_EMPTY_RESPONSE` cases with backend restarts, frontend dev-server rebuilds, or tunnel disconnects.
- [ ] Verify whether auth/login failures happen in direct local use or only inside TestSprite tunnel.
- [ ] If local runtime is stable, classify these as CI or tunnel noise and avoid feature-code churn.
- [ ] If local runtime is unstable, fix the actual failing boundary such as dev-server crashes, stale API base URL, or request timeout handling.

**Verification:** A clear rule exists for which failures block release and which are ignored as external runner noise.

---

## Task 8: Add Regression Gate

**Outcome:** Prevent the same bug classes from reopening.

- [ ] Add backend targeted tests for messages, events availability, and admin user search.
- [ ] Add frontend targeted checks for login redirect, `/messages` page load, and admin user detail navigation.
- [ ] Re-run TypeScript validation and the smallest relevant backend test slices.
- [ ] Re-run TestSprite only for the previously failing product-bug cases before full-suite retry.
- [ ] After targeted fixes pass, re-run the full frontend TestSprite pack in small batches again.

**Verification:** Previously failing product-bug cases are green before spending time on another 47-case full pass.

---

## Recommended Order

1. Messaging 500
2. Dashboard routing mismatch
3. Admin users search/detail
4. Events seed and details flow
5. Quest discovery expectation cleanup
6. Runtime instability classification
7. Targeted regression suite
8. Full TestSprite rerun

## Release Notes for This Plan

- Treat TC006-TC010 class failures as non-actionable until local runtime disproves tunnel noise.
- Treat TC016 as expected behavior unless product decides class selection should be available below level 5.
- Treat missing `Load more` as a product decision first, not an automatic bug.
- Prefer fixing deterministic seeded-data coverage over weakening assertions in E2E.