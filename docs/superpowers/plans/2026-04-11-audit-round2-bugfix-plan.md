# Audit Round 2 — Bugfix Plan

**Date:** 2026-04-11  
**Source:** Three parallel audits (Security, Backend, Frontend)

---

## Phase 0 — Critical Runtime Crashes (3 tasks)

### 0.1 `assign_freelancer` SELECT missing columns → KeyError crash
- **File:** `backend/app/services/quest_service.py` ~L620
- **Bug:** SELECT only fetches `id, client_id, status` but code accesses `quest["budget"]`, `quest["currency"]`, `quest["title"]`
- **Impact:** Every freelancer assignment crashes the server
- **Fix:** Change SELECT to `SELECT id, client_id, status, budget, currency, title FROM quests WHERE id = $1 FOR UPDATE`

### 0.2 `cancel_quest` SELECT missing `currency` → KeyError crash
- **File:** `backend/app/services/quest_service.py` ~L1228
- **Bug:** SELECT fetches `id, client_id, status, assigned_to, title` but `wallet_service.refund_hold` accesses `quest["currency"]`
- **Impact:** Every quest cancellation with escrow crashes
- **Fix:** Add `currency` to SELECT: `SELECT id, client_id, status, assigned_to, title, currency FROM quests...`

### 0.3 `cancel_quest` notification uses wrong kwargs → TypeError crash
- **File:** `backend/app/services/quest_service.py` ~L1273
- **Bug:** Passes `type="quest_cancelled"` and `link=f"/quests/{quest_id}"` — but `create_notification()` has no `type` or `link` params. Expected: `event_type=` instead of `type=`. This causes `TypeError: unexpected keyword argument 'type'`
- **Fix:** Change to `event_type="quest_cancelled"` and remove `link=` kwarg

---

## Phase 1 — High Severity (4 tasks)

### 1.1 `.env.example` duplicate blocks + insecure defaults
- **File:** `.env.example`
- **Bug:** File has two blocks; second block contains `SECRET_KEY=change-me-in-production`, `JWT_EXPIRE_MINUTES=30` (should be 5), `DEBUG=True` (contradicts first block)
- **Fix:** Consolidate into one canonical block, set `JWT_EXPIRE_MINUTES=5`, remove explicit `SECRET_KEY=change-me-in-production`

### 1.2 `profile/setup/page.tsx` unsafe `(err as ApiError).detail` cast
- **File:** `frontend/src/app/profile/setup/page.tsx` ~L145
- **Fix:** Replace with `getApiErrorMessage(err, "Не удалось сохранить.")`

### 1.3 `quests/templates/page.tsx` unsafe error cast
- **File:** `frontend/src/app/quests/templates/page.tsx` ~L223
- **Bug:** `(err as { detail?: string }).detail` — ad-hoc type cast
- **Fix:** Replace with `getApiErrorMessage(err, "Не удалось обновить шаблон")`

### 1.4 Raid quests store `platform_fee_percent=0` → zero platform revenue
- **File:** `backend/app/services/quest_service.py` ~L1785
- **Bug:** `Decimal("0")` is truthy, so `split_payment` never falls back to `settings.PLATFORM_FEE_PERCENT`
- **Fix:** At confirmation time in `confirm_quest_completion`, check `fee_percent` and substitute default if zero:  
  ```python
  fee_snapshot = quest.get("platform_fee_percent")
  if not fee_snapshot or Decimal(str(fee_snapshot)) <= 0:
      fee_snapshot = Decimal(settings.PLATFORM_FEE_PERCENT)
  ```

---

## Phase 2 — Medium Severity (14 tasks)

### 2.1–2.3 Missing rate limits: disputes, templates, saved searches/classes/users-me
- **Files:** `disputes.py` (3 GET endpoints), `templates.py` (2 GET), `saved_searches.py` (1 GET), `classes.py` (4 GET), `users.py` GET /me
- **Fix:** Add `check_rate_limit(get_client_ip(request), action="...", limit=60, window_seconds=60)` + `request: Request` param

### 2.4 Training quest notification outside parent transaction
- **File:** `backend/app/services/quest_service.py` ~L1655
- **Fix:** Move notification inside the main `async with conn.transaction():` block

### 2.5 `review_service.create_review` — quest row read without FOR SHARE
- **File:** `backend/app/services/review_service.py` ~L69
- **Fix:** Add `FOR SHARE` to the SELECT

### 2.6 `dispute_service.resolve_dispute` — `partial_percent=0.0` passes check
- **File:** `backend/app/services/dispute_service.py` ~L285
- **Fix:** Change to `if partial_percent is None or partial_percent <= 0 or partial_percent >= 100`

### 2.7 WebSocket endpoints lack message size limits / connection caps
- **File:** `backend/app/api/v1/endpoints/ws.py`
- **Fix:** Set `max_size` on ws recv, add per-user connection cap in WSManager

### 2.8 `SavedSearchForm.tsx` — `err instanceof Error` pattern
- **File:** `frontend/src/components/growth/SavedSearchForm.tsx` ~L34
- **Fix:** `setError(getApiErrorMessage(err, "Не удалось сохранить поиск"))`

### 2.9 `RageMode.tsx` — `err instanceof Error` pattern
- **File:** `frontend/src/components/rpg/RageMode.tsx` ~L50
- **Fix:** `setError(getApiErrorMessage(err, "Ошибка активации"))`

### 2.10 `EventLeaderboard.tsx` — `err instanceof Error` pattern
- **File:** `frontend/src/components/events/EventLeaderboard.tsx` ~L41
- **Fix:** `setError(getApiErrorMessage(err, "Ошибка загрузки"))`

### 2.11–2.13 Silent `.catch(() => {})` — abilities, shortlist (2 files)
- **Files:** `quests/[id]/page.tsx` ~L118, `users/[id]/page.tsx` ~L285, `marketplace/page.tsx` ~L410
- **Fix:** Replace with `.catch((e) => console.warn("Failed to load ...:", e))`

### 2.14 `admin/withdrawals/page.tsx` — hardcoded error strings (3 catch blocks)
- **File:** `frontend/src/app/admin/withdrawals/page.tsx` ~L68, ~L97, ~L113
- **Fix:** Import `getApiErrorMessage`, replace hardcoded strings

---

## Phase 3 — Low Severity (10 tasks)

### 3.1 `ProfileUpdateRequest.skills` items lack per-item length constraint
- **File:** `backend/app/api/v1/endpoints/users.py` ~L27
- **Fix:** Add `@field_validator("skills")` enforcing `max_length=50` per item

### 3.2 `SavedSearchCreate.filters_json` accepts unbounded data
- **File:** `backend/app/models/lifecycle.py` ~L67
- **Fix:** Add validator limiting key count (≤20) and depth (≤2)

### 3.3 `AnalyticsEventIngest.properties` unbounded on public endpoint
- **File:** `backend/app/models/analytics.py` ~L19
- **Fix:** Add validator limiting key count (≤30), total size (≤4KB)

### 3.4 `saved_searches_service.create_saved_search` — TOCTOU race on count limit
- **File:** `backend/app/services/saved_searches_service.py` ~L43
- **Fix:** Wrap in transaction or use advisory lock

### 3.5 `shortlist_service` — mutations without transaction boundary
- **File:** `backend/app/services/shortlist_service.py`
- **Fix:** Wrap in `async with conn.transaction()`

### 3.6 `dispute_service._grant_dispute_resolution_xp` — no badge check or trust score refresh
- **File:** `backend/app/services/dispute_service.py` ~L563
- **Fix:** Add `badge_service.check_and_award()` and `trust_score_service.refresh_trust_score()` calls

### 3.7 `user_id` reflected in error messages
- **File:** `backend/app/api/v1/endpoints/users.py` ~L561
- **Fix:** Use generic `"User not found"` without reflecting input

### 3.8 `QuestCreationWizard.tsx` — manual ApiError extraction instead of `getApiErrorMessage`
- **File:** `frontend/src/components/quests/QuestCreationWizard.tsx` ~L275
- **Fix:** Replace manual chain with `getApiErrorMessage(err, "Не удалось создать квест.")`

### 3.9 `admin/dashboard/page.tsx` — missing cleanup, hardcoded error
- **File:** `frontend/src/app/admin/dashboard/page.tsx` ~L94
- **Fix:** Wrap `reload` in `useCallback`, add `cancelled` guard, use `getApiErrorMessage`

### 3.10 Empty `catch {}` blocks in `quests/[id]/page.tsx`
- **File:** `frontend/src/app/quests/[id]/page.tsx` (3 places)
- **Fix:** Add `console.warn` inside each catch

---

## Totals

| Phase | Severity | Count |
|-------|----------|-------|
| 0 | Critical | 3 |
| 1 | High | 4 |
| 2 | Medium | 14 |
| 3 | Low | 10 |
| **Total** | | **31** |

## Execution Order

1. **Phase 0 first** — literal runtime crashes, must fix before any deployment
2. **Phase 1** — financial loss (raid fees) + security hygiene
3. **Phase 2** — consistency, rate limits, error handling
4. **Phase 3** — polish, validation, minor robustness
