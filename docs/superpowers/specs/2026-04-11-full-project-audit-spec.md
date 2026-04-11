# QuestionWork — Full Project Audit Spec (April 2026)

**Date:** 2026-04-11  
**Status:** Complete  
**Scope:** Security + Backend + Frontend deep audit  
**Method:** Three parallel automated audits (Security Review, Backend Specialist, Frontend Specialist)

---

## 1. Purpose

Comprehensive audit of all known and unknown issues in the QuestionWork codebase as of April 2026. Updates and supersedes the March 2026 audit (all 7 H-issues confirmed fixed).

---

## 2. Historical Issues — All Resolved ✅

| ID | Issue | Date Fixed |
|----|-------|-----------|
| H-01 | TOTP setup skips IP allowlist | pre-April 2026 |
| H-02 | QuestUpdate.budget ge=0 | pre-April 2026 |
| H-03 | Platform fee at payout | pre-April 2026 |
| H-04 | custom_xp unbounded | pre-April 2026 |
| H-05 | 5 stub character classes | pre-April 2026 |
| H-06 | Class confirm trial-expiry | pre-April 2026 |
| H-07 | Delivery URL HTTP | pre-April 2026 |

---

## 3. Security Audit Findings

### 3.1 Admin Security
- **A-1 (High):** `ADMIN_IP_ALLOWLIST` defaults to empty → all IPs allowed in production. File: `config.py`.
- **A-2 (Medium):** `.env.example` ships `ADMIN_TOTP_REQUIRED=false`. Copy-paste deployment risk.

### 3.2 Rate Limiting Gaps
- **R-1 (Low):** `POST /auth/logout` — no rate limit.
- **R-2 (Medium):** `POST /auth/refresh` — no rate limit. Enables token rotation abuse.
- **R-3 (Low):** `POST /users/onboarding/complete` — no rate limit.

### 3.3 Auth/JWT
- **J-1 (Medium):** `COOKIE_SECURE=false` in `.env.example`. Production cookie over HTTP risk.
- Token storage, refresh rotation, TOTP replay protection — all correct.

### 3.4 SQL Injection — Clean ✅
All queries use asyncpg parameterized placeholders. f-strings only on constant column lists.

### 3.5 Hardcoded Secrets — Clean ✅
`SECRET_KEY` validated at startup (min 32 chars + entropy). Docker Compose uses `${VAR:?error}`.

---

## 4. Backend Audit Findings

### 4.1 Critical
| ID | Issue | File |
|----|-------|------|
| B-01 | Notifications after `confirm_quest_completion` run outside the main financial transaction. Silent `except Exception` masks failures | `quest_service.py:1155` |

### 4.2 High
| ID | Issue | File |
|----|-------|------|
| B-02 | `cancel_quest` doesn't handle `assigned`/`in_progress` quests | `quest_service.py:1239` |
| B-03 | `GET /quests/{id}/history` — no rate limit | `quests.py:243` |
| B-04 | `GET /quests/{id}/applications` — no rate limit | `quests.py:487` |
| B-05 | `POST /users/onboarding/complete` — no rate limit | `users.py:408` |
| B-06 | Learning endpoints `POST /learning/*` — no auth required | `learning.py` |
| B-07 | `GET /meta/world` — no rate limit | `meta.py:12` |
| B-08 | `GET /quests/chains/*` (3 endpoints) — no rate limit | `quests.py:752+` |

### 4.3 Medium
| ID | Issue | File |
|----|-------|------|
| B-09 | `cancel_quest` for `revision_requested` — no freelancer notification | `quest_service.py:1239` |
| B-10 | `GET /quests/{id}/history` uses `get_optional_user` instead of `require_auth` | `quests.py:243` |
| B-11 | `apply_to_quest` SELECT misses `required_portfolio`, `is_urgent` → class restriction bypassed | `quest_service.py:549` |
| B-12 | `review_service` XP fallback skips `check_level_up()` | `review_service.py:111` |
| B-13 | `GET /guilds/{slug}` — no rate limit | `marketplace.py:29` |
| B-14 | `UserCreate.role` silently downgrades `admin` instead of rejecting | `user.py:203` |
| B-15 | `confirm_quest_completion` budget type-coercion fragility | `quest_service.py:958` |

### 4.4 Low
| ID | Issue | File |
|----|-------|------|
| B-16 | f-string SQL patterns safe but fragile | `admin_service.py:711` |
| B-17 | In-memory refresh store lock inconsistency | `security.py:147` |
| B-18 | `GET /reviews/check/{quest_id}` — no rate limit | `reviews.py:115` |
| B-19 | Same IP bucket for all quest-read rate limits | `quests.py:76` |
| B-20 | `TokenResponse.model_dump` email strip is fragile | `user.py:240` |
| B-21 | `DEV_DATABASE_URL` hardcoded with `postgres:postgres` (dev only) | `config.py:14` |

---

## 5. Frontend Audit Findings

### 5.1 Critical
| ID | Issue | File |
|----|-------|------|
| F-01 | `handleApplySubmit` missing try/catch — unhandled promise rejection | `quests/page.tsx:176` |
| F-02 | QuestChat hardcodes WebSocket URL to `ws://127.0.0.1:8001` | `QuestChat.tsx:28` |

### 5.2 High
| ID | Issue | File |
|----|-------|------|
| F-03 | Events pages use `err instanceof Error` instead of `getApiErrorMessage` | `events/page.tsx:56`, `events/[id]/page.tsx:58` |
| F-04 | Events pages use `alert()` for join errors | `events/page.tsx:107`, `events/[id]/page.tsx:83` |
| F-05 | Marketplace compare page `(err as ApiError).detail` without guard | `marketplace/compare/page.tsx:76` |
| F-06 | No Error Boundaries on 8+ complex pages (spec M-01) | Multiple pages |
| F-07 | Middleware only protects `/profile` — auth-required pages flash content | `middleware.ts` |

### 5.3 Medium
| ID | Issue | File |
|----|-------|------|
| F-08 | WalletPanel unmount race condition (spec M-03) | `WalletPanel.tsx:82` |
| F-09 | `analytics.ts` uses raw `fetch()` — no auth token | `analytics.ts:62` |
| F-10 | Admin dashboard missing `reload` in useEffect deps | `admin/dashboard/page.tsx:111` |
| F-11 | Users list page hardcodes error message | `users/page.tsx:84` |
| F-12 | Quest templates page hardcodes error message | `quests/templates/page.tsx:91` |
| F-13 | Admin withdrawals page hardcodes error message | `admin/withdrawals/page.tsx:71` |
| F-14 | `refreshSession()` no retry on 429/503 → immediate logout | `api.ts:867` |
| F-15 | Profile page silently swallows secondary request errors | `profile/page.tsx` |

### 5.4 Low
| ID | Issue | File |
|----|-------|------|
| F-16 | `STORAGE_KEY_USER` duplicated in `api.ts` and `AuthContext.tsx` | Two files |
| F-17 | Notifications page fetches directly instead of `useNotifications()` | `notifications/page.tsx:72` |

---

## 6. Positive Findings (Not Broken)

- All SQL queries are parameterized — no injection risk
- JWT tokens stored in memory, not localStorage
- Refresh token in httpOnly cookie with rotation
- Admin TOTP replay protection via Redis
- `fetchApiWithRetry` correctly retries 429/503 for idempotent methods
- `check_level_up()` called after all primary XP grant paths
- All 6 character classes fully implemented
- Rate limiting bypass explicitly blocked in production
- Docker Compose uses required env vars (`${VAR:?error}`)

---

*Matching implementation plan: `docs/superpowers/plans/2026-04-11-full-project-audit-bugfix-plan.md`*
