# Full Project Audit Report — QuestionWork
**Date:** 2026-03-13  
**Auditor:** Automated Principal Staff Engineer Audit  
**Scope:** Complete codebase — backend, frontend, database, infra

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| **Production Readiness** | ~78% |
| **P0 (Critical)** | 3 |
| **P1 (High)** | 12 |
| **P2 (Medium)** | 16 |
| **P3 (Low)** | 8 |
| **Estimated Total Fix Effort** | ~32h (M-L) |
| **Backend Tests** | 582 passed, 0 failed |
| **Frontend TypeScript** | 0 errors |

**Top Risk Areas:**
1. Refresh token race condition (session duplication)
2. Force-complete payment edge case (unpaid freelancer)
3. Commission rounding drift (cent-level loss at scale)
4. Frontend money display uses float (precision loss)

**Overall Assessment:** The codebase is structurally sound with mature patterns (escrow-first payments, dual-entry ledger, TOTP 2FA, bcrypt+JWT auth, comprehensive rate limiting). However, several edge-case race conditions and rounding issues in money flows need fixing before production scale. Security posture is strong with a few gaps (CSP header, TOTP key isolation).

---

## 2. Audit Coverage

### Modules Verified

| Module | Files Reviewed | Depth |
|--------|---------------|-------|
| Auth (JWT/refresh/TOTP) | security.py, auth.py, deps.py, auth_service.py | Deep |
| Wallet (escrow/split/withdraw) | wallet_service.py, wallet.py | Deep |
| Quest lifecycle | quest_service.py, quests.py | Deep |
| Admin operations | admin_service.py, admin.py | Deep |
| Config/security settings | config.py, ratelimit.py, redis_client.py | Deep |
| All 18 endpoint files | endpoints/*.py | Full |
| Frontend API layer | api.ts, types/index.ts | Deep |
| Frontend auth context | AuthContext.tsx, authEvents.ts | Deep |
| Frontend hooks | useNotifications.ts, useMyClass.ts, useXpToast.ts | Full |
| Frontend components (13 files) | Admin, quests, wallet, layout | Full |
| Database schema | models.py, 29 migrations | Full |
| Alembic config | env.py, versions/ | Full |
| XP/rewards | rewards.py | Medium |
| Frontend libs | currency.ts, xp.ts, adminTotp.ts | Full |

### Tests/Commands Used
- `pytest tests/ --no-cov -q` → 582 passed
- `npx tsc --noEmit` → 0 errors
- `alembic heads` → single head verified
- Manual code review of all 18 endpoint files, 21 service files, 11 model files

### Not Verified
- E2E integration tests (scripts/*.ps1) — not executed (require running servers)
- Load testing (locustfile.py) — not executed
- Docker compose setup — reviewed config only, not deployed
- Email service — reviewed code, not tested delivery
- Background scripts (process_withdrawals.py, etc.) — reviewed code only

---

## 3. P0 — Critical

### P0-1: Refresh Token Race Condition
- **Severity:** P0 | **Effort:** M (2-4h)
- **Location:** [backend/app/core/security.py](backend/app/core/security.py) lines 155-190, [backend/app/api/v1/endpoints/auth.py](backend/app/api/v1/endpoints/auth.py) lines 264-275
- **Problem:** Two concurrent `/refresh` requests with the same token both pass `verify_refresh_token()` then both create new tokens. Result: two valid refresh tokens → session duplication.
- **Risk:** Attacker with one stolen refresh token can generate unlimited sessions.
- **Proof:** `verify_refresh_token()` reads, `revoke_refresh_token()` deletes, `create_refresh_token()` writes — three separate operations with no locking. A context switch between verify and revoke allows both threads to succeed.
- **Fix:** Create atomic `rotate_refresh_token()` using Redis pipeline (GET+DELETE atomic) or threading lock for in-memory store.
- **Acceptance:** Concurrent refresh test → at most one thread gets valid user_id.

### P0-2: force_complete skip_escrow=True Still Attempts Payment
- **Severity:** P0 | **Effort:** S (1h)  
- **Location:** [backend/app/services/admin_service.py](backend/app/services/admin_service.py) lines 570-630
- **Problem:** When `skip_escrow=True` and no escrow hold exists, code proceeds to `split_payment()` which attempts direct debit from client. If client has insufficient balance → exception, but quest already marked confirmed. Freelancer unpaid.
- **Risk:** Data inconsistency — quest confirmed without payment.
- **Fix:** When `skip_escrow=True` and no hold, skip `split_payment()` entirely. Return `payment_skipped: true`.
- **Acceptance:** Test with skip_escrow=True + no hold → no split_payment call, payment_skipped flag set.

### P0-3: PLATFORM_USER_ID Guard Missing in split_payment
- **Severity:** P0 | **Effort:** S (<1h)
- **Location:** [backend/app/services/wallet_service.py](backend/app/services/wallet_service.py) lines 530-545
- **Problem:** `split_payment()` credits platform wallet assuming `PLATFORM_USER_ID` user exists. If deleted → FK violation → transaction rollback → freelancer payment also rolls back.
- **Risk:** Freelancer payment fails silently when platform user misconfigured.
- **Fix:** Check `SELECT 1 FROM users WHERE id = $1` at start of split_payment. Raise ValueError if missing.
- **Acceptance:** Test with missing platform user → ValueError raised before any credits.

---

## 4. P1 — High

### P1-1: TOTP Key Derived from SECRET_KEY
- **Severity:** P1 | **Effort:** M
- **Location:** [backend/app/core/security.py](backend/app/core/security.py) lines 245-251
- **Problem:** `_totp_fernet_key()` uses `sha256(SECRET_KEY)`. If SECRET_KEY leaks, all TOTP secrets compromised.
- **Fix:** Add `TOTP_ENCRYPTION_KEY` config; use domain-separated derivation.

### P1-2: Idempotency Key Returns Rejected Withdrawal
- **Severity:** P1 | **Effort:** S
- **Location:** [backend/app/services/wallet_service.py](backend/app/services/wallet_service.py) lines 494-508
- **Problem:** Idempotency check returns rejected/completed withdrawals as if valid. Frontend confused.
- **Fix:** Only return for `status='pending'`; raise ValueError for rejected/completed.

### P1-3: Commission Rounding Invariant Broken
- **Severity:** P1 | **Effort:** S
- **Location:** [backend/app/services/wallet_service.py](backend/app/services/wallet_service.py) lines 495-500
- **Problem:** `quantize_money(gross - fee)` double-rounds, breaking `fee + payout == gross` invariant.
- **Fix:** `freelancer_amount = gross_amount - platform_fee` without re-quantizing.

### P1-4: Missing CSP Header
- **Severity:** P1 | **Effort:** S
- **Location:** [backend/app/main.py](backend/app/main.py) lines 294-300
- **Problem:** No Content-Security-Policy header on API responses.
- **Fix:** Add restrictive CSP for API: `default-src 'none'; frame-ancestors 'none'`.

### P1-5: XP Level Calculation Uses Float
- **Severity:** P1 | **Effort:** S
- **Location:** [backend/app/core/rewards.py](backend/app/core/rewards.py) line 188
- **Problem:** `(current_xp / 10) ** 0.5` uses float — non-deterministic for large XP.
- **Fix:** Use `math.isqrt(current_xp // 10) + 1`.

### P1-6: leave_guild Missing Rate Limit
- **Severity:** P1 | **Effort:** S
- **Location:** [backend/app/api/v1/endpoints/marketplace.py](backend/app/api/v1/endpoints/marketplace.py) lines 75-85
- **Problem:** Only POST endpoint in marketplace.py without rate limiting.
- **Fix:** Add `check_rate_limit()`.

### P1-7: Admin Wallet Adjustment Uses 'income' tx_type
- **Severity:** P1 | **Effort:** S
- **Location:** [backend/app/services/admin_service.py](backend/app/services/admin_service.py) lines 690-700
- **Problem:** Admin grants indistinguishable from quest earnings in ledger.
- **Fix:** Use `tx_type="admin_adjust"`.

### P1-8: Quest Slot Count Includes 'completed'
- **Severity:** P1 | **Effort:** S
- **Location:** [backend/app/services/quest_service.py](backend/app/services/quest_service.py) lines 334-345, 395-404
- **Problem:** Freelancers stuck at slot limit while waiting for slow client confirmation.
- **Fix:** Exclude 'completed' from active slot count SQL.

### P1-9: Stale Exchange Rates Hardcoded
- **Severity:** P1 | **Effort:** M
- **Location:** [frontend/src/lib/currency.ts](frontend/src/lib/currency.ts) lines 14-20
- **Problem:** Static `rateFromRUB` values will be wrong immediately.
- **Fix:** Fetch rates from backend endpoint or remove conversion feature until API available.

### P1-10: authEvents.ts Single Handler Overwrite
- **Severity:** P1 | **Effort:** S
- **Location:** [frontend/src/lib/authEvents.ts](frontend/src/lib/authEvents.ts) line 12
- **Problem:** `_logoutHandler` overwritten on each registration — old handlers lost.
- **Fix:** Return cleanup function from `registerLogoutHandler`.

### P1-11: Silent Error Swallowing in useMyClass
- **Severity:** P1 | **Effort:** S
- **Location:** [frontend/src/hooks/useMyClass.ts](frontend/src/hooks/useMyClass.ts) lines 27-29
- **Problem:** Catch block hides API errors — user sees "no class" instead of error.
- **Fix:** Expose `error` state in return type.

### P1-12: Silent Error Swallowing in WorldMetaContext
- **Severity:** P1 | **Effort:** S
- **Location:** [frontend/src/context/WorldMetaContext.tsx](frontend/src/context/WorldMetaContext.tsx) lines 25-27
- **Problem:** Same pattern as useMyClass — errors hidden.
- **Fix:** Add error state to context.

---

## 5. P2 — Medium

### P2-1: useXpToast Timer Memory Leak
- **Location:** [frontend/src/hooks/useXpToast.ts](frontend/src/hooks/useXpToast.ts) lines 36-47
- `setTimeout` fires after unmount → React memory warning.
- **Fix:** useEffect cleanup to clear timer.

### P2-2: useNotifications Visibility Race
- **Location:** [frontend/src/hooks/useNotifications.ts](frontend/src/hooks/useNotifications.ts) lines 43-49
- Initial fetch skipped if tab hidden on mount.
- **Fix:** Call fetch() before setting visibleRef.

### P2-3: WalletPanel Float Precision
- **Location:** [frontend/src/components/rpg/WalletPanel.tsx](frontend/src/components/rpg/WalletPanel.tsx) line 95
- `parseFloat(withdrawAmount)` for money.
- **Fix:** Validate as string, convert once.

### P2-4: Admin EditUserModal XP Allows Negative
- **Location:** [frontend/src/components/admin/EditUserModal.tsx](frontend/src/components/admin/EditUserModal.tsx) line 372
- XP input has no min attribute.
- **Fix:** Add `min={1}` and validation.

### P2-5: EditQuestModal Force-Complete No Confirmation
- **Location:** [frontend/src/components/admin/EditQuestModal.tsx](frontend/src/components/admin/EditQuestModal.tsx) lines 178-195
- **Fix:** Add `window.confirm()` before force actions.

### P2-6: Quest Detail Double-Submit
- **Location:** [frontend/src/app/quests/[id]/page.tsx](frontend/src/app/quests/%5Bid%5D/page.tsx) lines 261-288
- Complete/revision forms can be double-submitted.
- **Fix:** Add `submitting` state + button disable.

### P2-7: Quest Detail loadQuest Race Condition
- **Location:** [frontend/src/app/quests/[id]/page.tsx](frontend/src/app/quests/%5Bid%5D/page.tsx) lines 61-108
- No cleanup flag for loadQuest effect — stale data on rapid navigation.
- **Fix:** Add `cancelled` flag in useEffect cleanup.

### P2-8: Refresh Token Eviction Ignores Expired
- **Location:** [backend/app/core/security.py](backend/app/core/security.py) lines 170-180
- LRU eviction may drop valid tokens while expired ones remain.
- **Fix:** Prune expired tokens before LRU eviction.

### P2-9: TOTP Error Leaks Implementation Details
- **Location:** [backend/app/api/deps.py](backend/app/api/deps.py) lines 147-151
- Error message says "possible legacy plaintext value" — information disclosure.
- **Fix:** Generic error message; internal log only.

### P2-10: Admin IP Log Includes user_id
- **Location:** [backend/app/api/deps.py](backend/app/api/deps.py) lines 234-238
- Log leaks admin user_id on IP violation.
- **Fix:** Log IP only, not user identity.

### P2-11: Request Body Size Limit Silent Truncation
- **Location:** [backend/app/main.py](backend/app/main.py) lines 213-267
- Exceeding body limit returns empty body, not 413 error.
- **Fix:** Return 413 immediately.

### P2-12: Missing GIN Index on users.skills
- **Location:** Database schema
- **Fix:** Alembic migration adding GIN index.

### P2-13: Missing CHECK Constraints on RPG Tables
- **Location:** Database schema (user_class_progress, users.review_count)
- **Fix:** Alembic migration adding CHECKs.

### P2-14: Batch Withdrawal Approval Race
- **Location:** [frontend/src/app/admin/withdrawals/page.tsx](frontend/src/app/admin/withdrawals/page.tsx) lines 145-163
- Sequential loop allows re-click before completion.
- **Fix:** Disable buttons during batch operation.

### P2-15: ADMIN_TOTP_REQUIRED Defaults False
- **Location:** [backend/app/core/config.py](backend/app/core/config.py) line 47
- Dangerous if accidentally deployed without setting.
- **Mitigated:** Production validation rejects false.

### P2-16: CORS Regex in Dev Permissive
- **Location:** [backend/app/main.py](backend/app/main.py) lines 340-350
- Matches any port on localhost in dev.
- **Mitigated:** Only in development mode.

---

## 6. P3 — Low

| ID | Issue | Location | Fix |
|----|-------|----------|-----|
| P3-1 | bcrypt cost not explicit | security.py:85 | `gensalt(rounds=12)` |
| P3-2 | WorldMetaContext dependency array | WorldMetaContext.tsx:33 | Remove unused dep |
| P3-3 | Fetch timeout hardcoded 15s | api.ts:900 | Make configurable |
| P3-4 | ENUM rigidity in DB | Multiple migrations | Document; consider VARCHAR+CHECK |
| P3-5 | No pagination in messages | messages/page.tsx:44 | Add offset/limit UI |
| P3-6 | QuestApplication.proposed_price type inconsistency | api.ts:228 vs types/index.ts | Unify type |
| P3-7 | Rate limit eviction sorts by latest | ratelimit.py:108-115 | Sort by oldest |
| P3-8 | No global logout endpoint | auth.py | Future: session revocation |

---

## 7. Cross-Cutting Findings

### Repeated Patterns
1. **Silent error swallowing** — useMyClass, WorldMetaContext, and several components catch errors and set null. Pattern creates silent failures.
2. **Double-submit vulnerability** — At least 5 frontend forms (wallet withdrawal, quest completion, revision, batch approval, badge revoke) lack proper submission guards.
3. **Float ↔ Decimal boundary** — Backend correctly uses Decimal everywhere, but frontend normalizes via `toNumber()` which returns JS `number` (float64). Money display uses `toLocaleString()` which is OK for display but not for computation.

### Architectural Smells
1. **In-memory refresh store** — Production-ready but creates single-point-of-failure. Redis fallback is solid, but the in-memory path needs the threading lock (Task 1).
2. **Commission calculation location** — `split_payment()` in wallet_service handles commission. admin_service.py also calls it but with different error handling. Should be one canonical path.
3. **Notification side effects** — Post-commit notification pattern (quest_service.py lines 741-765) means notifications can be lost if second transaction fails. Acceptable trade-off, but should be documented.

### Contract Drift Themes
1. `QuestApplication.proposed_price` differs between api.ts (`number | undefined`) and types/index.ts (`MoneyAmount | null`).
2. admin_service tx_type='income' doesn't match expected audit trail semantics.

---

## 8. Prioritized Roadmap

| Batch | Tasks | Priority | Effort | Success Criteria |
|-------|-------|----------|--------|-----------------|
| **1 — Critical Security** | 1 (refresh race), 2 (platform guard), 3 (skip_escrow) | P0 | 4-6h | No concurrent session duplication; payment guard tests pass |
| **2 — Money & Security** | 4 (TOTP key), 5 (idempotency), 6 (commission), 7 (CSP) | P1 | 4-6h | Commission invariant holds; CSP header present; TOTP key isolated |
| **3 — Logic & Backend** | 8 (XP float), 9 (rate limit), 10 (tx_type), 11 (slot count) | P1 | 3-4h | isqrt deterministic; all POST endpoints rate-limited |
| **4 — Frontend Quality** | 12-17 (wallet float, timer, notifications, XP, confirm, double-submit) | P2 | 3-4h | tsc clean; build passes; no float money ops |
| **5 — Database Schema** | 18 (GIN), 19 (CHECKs), 20 (eviction) | P2 | 2-3h | Migrations applied; queries use index |
| **6 — Verification** | 21-23 (full test suite, tsc, build, alembic) | — | 1h | 582+ tests pass, tsc clean, build OK, single head |

---

## 9. Production Readiness Checklist

### Security ✅/❌
- [x] JWT with algorithm pinning and audience/issuer validation
- [x] bcrypt password hashing with timing-attack prevention
- [x] TOTP 2FA for admin with replay protection
- [x] Rate limiting on all POST/PATCH/DELETE (except 1 — Task 9)
- [x] Admin IP allowlist with production enforcement
- [ ] **CSP header missing** (Task 7)
- [ ] **TOTP key isolation** (Task 4)
- [ ] **Refresh token atomic rotation** (Task 1)

### Money/Data Integrity ✅/❌
- [x] Decimal arithmetic throughout backend
- [x] SELECT FOR UPDATE on all balance-modifying operations
- [x] Escrow-first design with proper hold/release/refund
- [x] Platform fee calculation with configurable percentage
- [ ] **Commission rounding invariant** (Task 6)
- [ ] **Platform user existence guard** (Task 2)
- [ ] **skip_escrow payment skip** (Task 3)
- [ ] **Idempotency key status check** (Task 5)

### Reliability ✅/❌
- [x] Connection pool with validation (SELECT 1)
- [x] Redis fallback to in-memory
- [x] Structured logging with OpenTelemetry
- [x] Health/readiness endpoints
- [ ] **Refresh token eviction** (Task 20)

### Frontend Contract Safety ✅/❌
- [x] Centralized fetchApi with token management
- [x] In-memory access token (not localStorage)
- [x] Money normalization via toNumber()
- [ ] **Float precision in withdrawal input** (Task 12)
- [ ] **Double-submit guards** (Tasks 12, 17)
- [ ] **Error state exposure in hooks** (addressed partially)

---

## 10. Immediate Next Actions

### Option A: Safest Fix Order
1. Batch 1 (P0 critical) → fix and test thoroughly
2. Batch 2 (P1 money) → commission + TOTP
3. Batch 3 (P1 logic) → backend cleanup
4. Batch 4-5 (P2) → frontend + DB
5. Full verification

### Option B: Fastest Path to Launch
1. Tasks 1, 2, 3 (P0) — 4h
2. Tasks 5, 6, 7 (money + CSP) — 2h
3. Tasks 12, 17 (frontend money + double-submit) — 2h
4. Skip P2 DB tasks (can deploy after launch)
5. Verification — 1h
**Total: ~9h to launch-ready**

### Option C: Correct Long-term Path
1. All P0 + P1 tasks (1-11) — 12h
2. All P2 tasks (12-20) — 8h
3. Full verification + staging test + load test — 4h
4. Create monitoring dashboards for money flows
5. Set up alerting on commission discrepancies
**Total: ~24h to fully hardened**
