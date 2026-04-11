# QuestionWork — Full Project Audit & Bugfix Plan

**Date:** 2026-04-11  
**Status:** Ready for execution  
**Scope:** Security, backend, frontend — all confirmed bugs from deep audit  
**Phases:** 0 → 4 (sequential)

---

## Audit Summary

Three parallel audits were run: Security, Backend, Frontend.  
All 7 historical spec issues (H-01 → H-07) are **already fixed**.  
Below are the **new** confirmed issues that must be addressed.

### Totals

| Area | Critical | High | Medium | Low |
|------|:--------:|:----:|:------:|:---:|
| Security | 0 | 1 | 3 | 1 |
| Backend | 1 | 8 | 7 | 6 |
| Frontend | 2 | 6 | 8 | 3 |
| **Total** | **3** | **15** | **18** | **10** |

---

## Phase 0 — Critical & Security Fixes
**Goal:** Eliminate all critical bugs and high-severity security issues.  
**Prerequisite:** None.

### Task 0.1 — Add startup guard for empty ADMIN_IP_ALLOWLIST in production [Security A-1]
- **File:** `backend/app/core/config.py`
- **Action:** In the `Settings` validator, if `ENVIRONMENT == "production"` and `ADMIN_IP_ALLOWLIST` is empty, raise `ValueError("ADMIN_IP_ALLOWLIST must be set in production")`.
- **Severity:** High
- [ ] Implement
- [ ] Test: set `ENVIRONMENT=production` + empty allowlist → app refuses to start

### Task 0.2 — Fix .env.example insecure defaults [Security A-2, J-1]
- **File:** `backend/.env.example`
- **Action:**
  - Change `ADMIN_TOTP_REQUIRED=false` → `ADMIN_TOTP_REQUIRED=true` with `# NEVER set false in production`
  - Change `COOKIE_SECURE=false` → `COOKIE_SECURE=true` with `# false only for local HTTP dev`
- **Severity:** Medium
- [ ] Implement

### Task 0.3 — Add rate limit to `POST /auth/refresh` [Security R-2]
- **File:** `backend/app/api/v1/endpoints/auth.py`
- **Action:** Add `check_rate_limit(ip, action="auth_refresh", limit=20, window_seconds=60)` at the top of the refresh endpoint.
- **Severity:** Medium
- [ ] Implement
- [ ] Test: call refresh 21 times → 429

### Task 0.4 — Add rate limit to `POST /auth/logout` [Security R-1]
- **File:** `backend/app/api/v1/endpoints/auth.py`
- **Action:** Add `check_rate_limit(ip, action="auth_logout", limit=10, window_seconds=60)`.
- **Severity:** Low
- [ ] Implement

### Task 0.5 — Fix `handleApplySubmit` missing try/catch [Frontend C-01]
- **File:** `frontend/src/app/quests/page.tsx`
- **Action:** Wrap `await applyToQuest(...)` in try/catch, set error state, close modal on failure.
- **Severity:** Critical
- [ ] Implement
- [ ] Test: disconnect backend → apply → user sees error toast, modal closes

### Task 0.6 — Fix QuestChat hardcoded WebSocket URL [Frontend C-02]
- **File:** `frontend/src/components/quests/QuestChat.tsx`
- **Action:** Replace `ws://127.0.0.1:8001` with dynamic WS URL derived from `NEXT_PUBLIC_API_URL` (replace `http` → `ws`, `https` → `wss`).
- **Severity:** Critical
- [ ] Implement
- [ ] Test: QuestChat connects via correct WS URL from env var

### Task 0.7 — Move notifications from `confirm_quest_completion` inside main transaction [Backend #1]
- **File:** `backend/app/services/quest_service.py`
- **Action:** Move notification creation calls into the existing `async with conn.transaction()` block instead of the separate post-commit block. Remove silent `except Exception`.
- **Severity:** Critical
- [ ] Implement
- [ ] Test: verify notifications are created atomically with the quest confirmation

---

## Phase 1 — High-Severity Backend & Frontend Fixes
**Goal:** Close all High-severity rate limiting gaps, auth issues, and frontend bugs.  
**Prerequisite:** Phase 0 complete.

### Task 1.1 — Add rate limits to unprotected GET endpoints [Backend #3-4, 7-9]
- **Files:** `backend/app/api/v1/endpoints/quests.py`, `backend/app/api/v1/endpoints/meta.py`
- **Action:** Add `_quest_read_rate_limit(request)` or equivalent to:
  - `GET /quests/{quest_id}/history` (line ~243)
  - `GET /quests/{quest_id}/applications` (line ~487)
  - `GET /quests/chains/list` (line ~752)
  - `GET /quests/chains/{chain_id}` (line ~765)
  - `GET /quests/chains/my-progress` (line ~797)
  - `GET /meta/world` (line ~12) — new rate limit: 60/60s per IP
- **Severity:** High
- [ ] Implement
- [ ] Test: exceed limits → 429

### Task 1.2 — Add rate limit to `POST /users/onboarding/complete` [Backend #5]
- **File:** `backend/app/api/v1/endpoints/users.py`
- **Action:** Add `check_rate_limit(ip, action="onboarding_complete", limit=5, window_seconds=60)`.
- **Severity:** High
- [ ] Implement

### Task 1.3 — Add auth requirement to learning endpoints [Backend #6]
- **File:** `backend/app/api/v1/endpoints/learning.py`
- **Action:** Add `current_user: UserProfile = Depends(require_auth)` to `POST /learning/voice-intro` and `POST /learning/chat`.
- **Severity:** High
- [ ] Implement
- [ ] Test: call without token → 401

### Task 1.4 — Add rate limit to `GET /guilds/{guild_slug}` [Backend #14]
- **File:** `backend/app/api/v1/endpoints/marketplace.py`
- **Action:** Add `check_rate_limit(ip, action="guild_detail", limit=60, window_seconds=60)`.
- **Severity:** Medium → borderline High
- [ ] Implement

### Task 1.5 — Fix events pages error type check [Frontend H-01]
- **Files:** `frontend/src/app/events/page.tsx`, `frontend/src/app/events/[id]/page.tsx`
- **Action:** Replace `err instanceof Error ? err.message : "Ошибка загрузки"` with `getApiErrorMessage(err)`.
- **Severity:** High
- [ ] Implement

### Task 1.6 — Replace `alert()` with inline error state in events pages [Frontend H-02, H-03]
- **Files:** `frontend/src/app/events/page.tsx`, `frontend/src/app/events/[id]/page.tsx`
- **Action:** Replace `alert(msg)` with `setJoinError(msg)` + render inline error message.
- **Severity:** High
- [ ] Implement

### Task 1.7 — Fix marketplace compare page error handling [Frontend H-04]
- **File:** `frontend/src/app/marketplace/compare/page.tsx`
- **Action:** Replace `(err as ApiError).detail` with `getApiErrorMessage(err)`.
- **Severity:** High
- [ ] Implement

### Task 1.8 — Protect auth-required pages with middleware [Frontend H-06]
- **File:** `frontend/src/middleware.ts`
- **Action:** Extend the `config.matcher` to include `/quests/create`, `/notifications`, `/messages`, `/admin/:path*`, `/disputes/:path*`.
- **Severity:** High
- [ ] Implement

---

## Phase 2 — Medium-Severity Bug Fixes
**Goal:** Logic fixes, missing notifications, UX improvements.  
**Prerequisite:** Phase 1 complete.

### Task 2.1 — Fix `apply_to_quest` missing SELECT columns [Backend #12]
- **File:** `backend/app/services/quest_service.py`
- **Action:** In `apply_to_quest`, add `required_portfolio, is_urgent` to the quest SELECT query so class restriction checks work correctly.
- **Severity:** Medium (bypasses berserker portfolio restriction)
- [ ] Implement
- [ ] Test: berserker user applies to quest with `required_portfolio=true` → blocked

### Task 2.2 — Add freelancer notification on quest cancellation [Backend #10]
- **File:** `backend/app/services/quest_service.py`
- **Action:** In `cancel_quest`, when status is `revision_requested`, emit a notification to the freelancer inside the transaction.
- **Severity:** Medium
- [ ] Implement

### Task 2.3 — Fix `get_quest_history` auth to use `require_auth` [Backend #11]
- **File:** `backend/app/api/v1/endpoints/quests.py`
- **Action:** Replace `get_optional_user` with `require_auth` for the quest history endpoint.
- **Severity:** Medium
- [ ] Implement

### Task 2.4 — Fix WalletPanel unmount race condition [Frontend M-01, Spec M-03]
- **File:** `frontend/src/components/rpg/WalletPanel.tsx`
- **Action:** Add `AbortController` to fetch calls. Pass `signal` to `fetchApi`. On unmount, call `controller.abort()`.
- **Severity:** Medium
- [ ] Implement

### Task 2.5 — Fix `analytics.ts` to use `fetchApi` [Frontend M-02]
- **File:** `frontend/src/lib/analytics.ts`
- **Action:** Replace raw `fetch()` with `fetchApiVoid()` for analytics ingest (keep `sendBeacon` as fallback for `beforeunload`).
- **Severity:** Medium
- [ ] Implement

### Task 2.6 — Fix error messages in list pages to use `getApiErrorMessage` [Frontend M-04, M-05, M-06]
- **Files:**
  - `frontend/src/app/users/page.tsx`
  - `frontend/src/app/quests/templates/page.tsx`
  - `frontend/src/app/admin/withdrawals/page.tsx`
- **Action:** Replace hardcoded error strings with `getApiErrorMessage(err)`.
- **Severity:** Medium
- [ ] Implement

### Task 2.7 — Add retry logic to `refreshSession()` [Frontend M-07]
- **File:** `frontend/src/lib/api.ts`
- **Action:** Add 1 retry on 429/503 with 1s delay in `refreshSession()` before logging the user out.
- **Severity:** Medium
- [ ] Implement

### Task 2.8 — Fix profile page to show error for failed secondary requests [Frontend M-08]
- **File:** `frontend/src/app/profile/page.tsx`
- **Action:** Replace `.catch(() => {})` with `.catch(err => setPartialError(...))` for badges, class, artifacts. Show a dismissible warning banner.
- **Severity:** Medium
- [ ] Implement

### Task 2.9 — Add rate limit to `GET /reviews/check/{quest_id}` [Backend #20]
- **File:** `backend/app/api/v1/endpoints/reviews.py`
- **Action:** Add `check_rate_limit(ip, action="review_check", limit=30, window_seconds=60)`.
- **Severity:** Low
- [ ] Implement

---

## Phase 3 — Error Boundaries & UX Polish
**Goal:** Prevent white-screen crashes. Clean up inconsistencies.  
**Prerequisite:** Phase 2 complete.

### Task 3.1 — Add Error Boundaries to complex pages [Frontend H-05, Spec M-01]
- **Action:** Wrap content in `<ErrorBoundary>` on:
  - `frontend/src/app/quests/[id]/page.tsx`
  - `frontend/src/app/profile/page.tsx`
  - `frontend/src/app/marketplace/page.tsx`
  - `frontend/src/app/admin/dashboard/page.tsx`
  - `frontend/src/app/messages/page.tsx`
  - `frontend/src/app/notifications/page.tsx`
  - `frontend/src/app/disputes/page.tsx`
  - `frontend/src/app/disputes/[id]/page.tsx`
- **Severity:** High (UX)
- [ ] Implement

### Task 3.2 — Deduplicate `STORAGE_KEY_USER` constant [Frontend L-01]
- **Files:** `frontend/src/lib/api.ts`, `frontend/src/context/AuthContext.tsx`
- **Action:** Export from `api.ts`, import in `AuthContext.tsx`.
- **Severity:** Low
- [ ] Implement

### Task 3.3 — Use `useNotifications()` hook in notifications page [Frontend L-02]
- **File:** `frontend/src/app/notifications/page.tsx`
- **Action:** Replace direct `getNotifications()` call with `useNotifications()` hook.
- **Severity:** Low
- [ ] Implement

---

## Phase 4 — Backend Logic Edge Cases
**Goal:** Fix non-urgent logic bugs.  
**Prerequisite:** Phase 3 complete.

### Task 4.1 — Fix `cancel_quest` for `assigned` status [Backend #2]
- **File:** `backend/app/services/quest_service.py`
- **Action:** Decide on business rule: allow cancellation of `assigned` quests (before work starts) with escrow refund? Or add an explicit error message? Add the chosen behavior + tests.
- **Severity:** High (business logic)
- [ ] Design decision
- [ ] Implement
- [ ] Test

### Task 4.2 — Fix `review_service` XP fallback level-up [Backend #13]
- **File:** `backend/app/services/review_service.py`
- **Action:** In the edge-case fallback XP grant path (reviewer row not found), call `check_level_up()` after the UPDATE.
- **Severity:** Medium (edge case)
- [ ] Implement
- [ ] Test

### Task 4.3 — Fix `UserCreate.role` to reject `admin` input [Backend #15]
- **File:** `backend/app/models/user.py`
- **Action:** Change validator from silent downgrade to `raise ValueError("Cannot set role to admin via registration")`.
- **Severity:** Medium
- [ ] Implement
- [ ] Test: POST `/auth/register` with `role=admin` → 400

### Task 4.4 — Fix in-memory refresh token store locking [Backend #19]
- **File:** `backend/app/core/security.py`
- **Action:** Use `_refresh_store_lock` in `create_refresh_token()` as well, not just `rotate_refresh_token()`.
- **Severity:** Low (dev-only)
- [ ] Implement

---

## Execution Rules

1. Implement exactly **one phase** at a time.
2. After each phase: run `pytest` (backend) + `tsc --noEmit` + `npm run build` (frontend).
3. Do not start the next phase until all tasks in the current phase pass.
4. Each task must include a test or manual verification step.
5. Critical items (Phase 0) block all other work.

---

## Already Fixed (No Action Needed)

| ID | Issue | Status |
|----|-------|--------|
| H-01 | TOTP setup skips IP allowlist | ✅ Fixed |
| H-02 | QuestUpdate.budget allows ge=0 | ✅ Fixed (`ge=100`) |
| H-03 | Platform fee at payout | ✅ Fixed (fee snapshot at creation) |
| H-04 | custom_xp unbounded | ✅ Fixed (field removed, `xp_reward` bounded 10–500) |
| H-05 | 5 stub character classes | ✅ Fixed (all 6 fully defined) |
| H-06 | Class confirm skips trial check | ✅ Fixed |
| H-07 | Delivery URL accepts HTTP | ✅ Fixed (validator rejects http://) |
| SQL injection | All queries parameterized | ✅ Clean |
| Token storage | In-memory JS variable | ✅ Correct |
| JWT security | Short TTL + refresh rotation | ✅ Correct |
| 429/503 retry | `fetchApiWithRetry` implemented | ✅ Correct |
