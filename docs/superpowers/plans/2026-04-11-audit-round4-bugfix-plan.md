# Audit Round 4 — Bug Fix Plan
**Date:** 2026-04-11  
**Scope:** Backend endpoints/services + frontend pages/components  
**Status:** Planning

---

## Summary

Round 4 found **10 issues** — all frontend, all the same pattern: `catch {}` with a hardcoded error string instead of `catch (err) { setError(getApiErrorMessage(err, "…")) }`. No critical backend issues (all `check_rate_limit` calls are properly awaited, all financial calculations use `Decimal`, no SQL injection vectors found).

---

## Phase 0 — Critical (0 issues)

None.

---

## Phase 1 — High (10 issues)

All 10 are `catch {}` blocks that swallow the real API error detail and show a hardcoded fallback string, losing diagnostic info. Three files also need the `getApiErrorMessage` import added.

### 1. `admin/logs/page.tsx` line 45
**File:** `frontend/src/app/admin/logs/page.tsx`  
**Issue:** `catch { setError("Не удалось загрузить логи.") }` — no variable, no `getApiErrorMessage`  
**Fix:** `catch (err) { setError(getApiErrorMessage(err, "Не удалось загрузить логи.")) }` + add `getApiErrorMessage` to the `adminGetLogs` import line

### 2. `admin/users/page.tsx` line 57
**File:** `frontend/src/app/admin/users/page.tsx`  
**Issue:** `catch { setError("Не удалось загрузить список пользователей.") }`  
**Fix:** `catch (err) { setError(getApiErrorMessage(err, "Не удалось загрузить список пользователей.")) }` + add `getApiErrorMessage` to the `adminGetUsers` import line

### 3. `admin/quests/page.tsx` line 65
**File:** `frontend/src/app/admin/quests/page.tsx`  
**Issue:** `catch { setError("Не удалось загрузить квесты.") }`  
**Fix:** `catch (err) { setError(getApiErrorMessage(err, "Не удалось загрузить квесты.")) }` + add `getApiErrorMessage` to the `adminGetQuests` import line

### 4. `admin/dashboard/page.tsx` line 122 — `handleCleanup`
**File:** `frontend/src/app/admin/dashboard/page.tsx`  
**Issue:** `catch { setCleanupMsg("Ошибка при очистке уведомлений.") }` — import already present  
**Fix:** `catch (err) { setCleanupMsg(getApiErrorMessage(err, "Ошибка при очистке уведомлений.")) }`

### 5. `quests/templates/page.tsx` line 100 — `load()`
**File:** `frontend/src/app/quests/templates/page.tsx`  
**Issue:** `catch { setError("Не удалось загрузить шаблоны") }` — import already present  
**Fix:** `catch (err) { setError(getApiErrorMessage(err, "Не удалось загрузить шаблоны")) }`

### 6. `quests/templates/page.tsx` line 165 — `handleCreate()`
**File:** `frontend/src/app/quests/templates/page.tsx`  
**Issue:** `catch { setError("Ошибка при создании шаблона") }`  
**Fix:** `catch (err) { setError(getApiErrorMessage(err, "Ошибка при создании шаблона")) }`

### 7. `quests/templates/page.tsx` line 254 — `handleDelete()`
**File:** `frontend/src/app/quests/templates/page.tsx`  
**Issue:** `catch { setError("Ошибка при удалении") }`  
**Fix:** `catch (err) { setError(getApiErrorMessage(err, "Ошибка при удалении")) }`

### 8. `quests/templates/page.tsx` line 275 — `handleUseTemplate()`
**File:** `frontend/src/app/quests/templates/page.tsx`  
**Issue:** `catch { setError("Не удалось создать квест из шаблона") }`  
**Fix:** `catch (err) { setError(getApiErrorMessage(err, "Не удалось создать квест из шаблона")) }`

### 9. `components/admin/EditUserModal.tsx` line 173 — `loadUser()`
**File:** `frontend/src/components/admin/EditUserModal.tsx`  
**Issue:** `catch { flash("Не удалось загрузить пользователя", "err") }` — import already present  
**Fix:** `catch (err) { flash(getApiErrorMessage(err, "Не удалось загрузить пользователя"), "err") }`

### 10. `components/admin/EditQuestModal.tsx` line 104 — `loadQuest()`
**File:** `frontend/src/components/admin/EditQuestModal.tsx`  
**Issue:** `catch { flash("Не удалось загрузить квест", "err") }` — local `getApiErrorMessage` already defined  
**Fix:** `catch (err) { flash(getApiErrorMessage(err, "Не удалось загрузить квест"), "err") }`

---

## Acceptable Silent Catches (no action required)

| Location | Reason |
|---|---|
| `quests/[id]/page.tsx` line 220 | Review status check; defaults to `false` is correct fallback |
| `quests/[id]/page.tsx` line 398 | Inner refresh after assign; outer catch shows error |
| `RecommendedTalentRail.tsx` | Non-critical UI rail; sets `[]` gracefully |
| `RecommendedQuestPanel.tsx` | Non-critical UI panel; sets `[]` gracefully |
| `QuestChat.tsx` lines 139, 146 | WS malformed payload + connection fallback; polling continues |
| `WalletBadge.tsx` | Comment: "Silently fail — badge just won't show a number" |
| `OnboardingWizard.tsx` line 239 | Comment: "Non-critical. The modal can retry later." |

---

## Backend Audit Results (all clean)

- ✅ All `check_rate_limit(` calls in endpoints are `await`ed (96 occurrences checked)
- ✅ All financial math uses `Decimal` with proper rounding
- ✅ Dynamic SQL ORDER BY clauses use whitelist dicts, not user input directly
- ✅ All mutation endpoints (POST/PATCH/DELETE) have rate limiting

---

## Validation Steps

```bash
# Frontend
cd frontend && npx tsc --noEmit 2>&1 | Select-Object -Last 10

# Backend
cd backend
$vpyth = (Resolve-Path ".\$((Get-Item '.\.v*' -ErrorAction SilentlyContinue | Select-Object -First 1).Name)\Scripts\python.exe")
& $vpyth -m pytest tests/test_rewards.py tests/test_security.py tests/test_classes.py -q --tb=short
```
