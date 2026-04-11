# Round 3 Audit — Bugfix Plan
**Date:** 2026-04-11  
**Auditor:** GitHub Copilot (direct — subagents rate-limited)  
**Scope:** Backend endpoints/services/models, frontend pages/components  

---

## Summary

| Phase | Severity | Count | Status |
|-------|----------|-------|--------|
| 0     | Critical | 3     | ⬜     |
| 1     | High     | 4     | ⬜     |
| 2     | Medium   | 5     | ⬜     |

**Total:** 12 issues

---

## Phase 0 — Critical (fix immediately, runtime breaks)

### 0.1 `disputes.py` — Missing `await` on 3 `check_rate_limit` calls

**File:** `backend/app/api/v1/endpoints/disputes.py`  
**Lines:** 88, 103, 224  
**Severity:** 🔴 Critical  
**Impact:** Rate limits silently unenforced — coroutine created but never awaited. Disputes GET endpoints have zero throttling despite the code appearing to have it.

**Current (line 88):**
```python
check_rate_limit(get_client_ip(request), action="dispute_read", limit=60, window_seconds=60)
```
**Fix:**
```python
await check_rate_limit(get_client_ip(request), action="dispute_read", limit=60, window_seconds=60)
```
Same fix at lines 103 and 224 (`admin_dispute_read`).

---

### 0.2 `OnboardingWizard.tsx` — `instanceof Error` hides API error detail

**File:** `frontend/src/components/onboarding/OnboardingWizard.tsx`  
**Line:** 187  
**Severity:** 🔴 Critical (for UX — onboarding errors silenced)  
**Impact:** When `updateMyProfile` or `completeOnboarding` returns a 400/422, ApiError is never instanceof Error, so the user sees "Ошибка сохранения онбординга" with no actionable info.

**Current:**
```typescript
setError(unknownError instanceof Error ? unknownError.message : "Ошибка сохранения онбординга");
```
**Fix:**
```typescript
setError(getApiErrorMessage(unknownError, "Ошибка сохранения онбординга"));
```

---

### 0.3 `AbilityPanel.tsx` — 2× `instanceof Error` hides API error detail

**File:** `frontend/src/components/rpg/AbilityPanel.tsx`  
**Lines:** 175, 190  
**Severity:** 🔴 Critical (ability activation errors silenced)

**Current (line 175):**
```typescript
.catch((e) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
```
**Current (line 190):**
```typescript
setToast({ msg: e instanceof Error ? e.message : "Ошибка", ok: false });
```
**Fix (both):** Use `getApiErrorMessage(e, fallback)`.

---

## Phase 1 — High severity

### 1.1 `users/page.tsx` — Hardcoded error, no `getApiErrorMessage`

**File:** `frontend/src/app/users/page.tsx`  
**Line:** 79  
**Severity:** 🟠 High  
**Impact:** API error detail lost; user gets "Не удалось загрузить список пользователей." regardless of actual error.

**Current:**
```typescript
} catch {
  setError("Не удалось загрузить список пользователей.");
}
```
**Fix:** Import and use `getApiErrorMessage`.

---

### 1.2 `profile/dashboard/page.tsx` — Hardcoded error, no `getApiErrorMessage`

**File:** `frontend/src/app/profile/dashboard/page.tsx`  
**Line:** 75  
**Severity:** 🟠 High

**Current:**
```typescript
} catch {
  setError("Не удалось загрузить данные");
}
```
**Fix:** `catch (err) { setError(getApiErrorMessage(err, "Не удалось загрузить данные")); }`

---

### 1.3 `WalletPanel.tsx` — Hardcoded error in catch

**File:** `frontend/src/components/rpg/WalletPanel.tsx`  
**Line:** 98  
**Severity:** 🟠 High

**Current:**
```typescript
} catch {
  setError("Не удалось загрузить кошелёк");
}
```
**Fix:** `catch (err) { setError(getApiErrorMessage(err, "Не удалось загрузить кошелёк")); }`

---

### 1.4 `quests/[id]/page.tsx` — Silent empty catch on `getQuestHistory` refresh

**File:** `frontend/src/app/quests/[id]/page.tsx`  
**Line:** 448  
**Severity:** 🟠 High  
**Impact:** After `publishQuest` succeeds, history refresh fails silently — user sees old history.

**Current:**
```typescript
try {
  const historyData = await getQuestHistory(quest.id);
  setHistory(historyData.history);
} catch {}
```
**Fix:**
```typescript
} catch (e) {
  console.warn("Failed to refresh quest history after publish", e);
}
```

---

## Phase 2 — Medium severity

### 2.1 `HomeClientSection.tsx` — Silently swallows profile load error

**File:** `frontend/src/components/home/HomeClientSection.tsx`  
**Line:** ~543  
**Severity:** 🟡 Medium  
**Impact:** If `getUserProfile` fails, the component silently uses the stale `user` object from context as a fallback — acceptable resilience, but should at least log.

**Current:**
```typescript
} catch {
  setProfile(user);
}
```
**Fix:**
```typescript
} catch (e) {
  console.warn("Failed to load profile, using auth context fallback", e);
  setProfile(user);
}
```

---

### 2.2 `profile/page.tsx` — Silently swallows class info load error

**File:** `frontend/src/app/profile/page.tsx`  
**Line:** ~316  
**Severity:** 🟡 Medium  
**Impact:** Silent failure; if class endpoint changes shape, error is never visible.

**Current:**
```typescript
} catch {
  classInfo = null;
}
```
**Fix:**
```typescript
} catch (e) {
  console.warn("Failed to load class info", e);
  classInfo = null;
}
```

---

### 2.3 `OnboardingWizard.tsx` — `handleSkip` swallows all errors silently

**File:** `frontend/src/components/onboarding/OnboardingWizard.tsx`  
**Line:** 226  
**Severity:** 🟡 Medium  
**Impact:** If `completeOnboarding()` or `updateMyProfile()` fails during skip, the wizard silently redirects to /quests with no user feedback. Onboarding may never be marked complete.

**Current:**
```typescript
} catch {
  router.push("/quests");
}
```
**Fix:** Add console.warn at minimum:
```typescript
} catch (e) {
  console.warn("Onboarding skip failed", e);
  router.push("/quests");
}
```

---

### 2.4 `notifications/page.tsx` — Preference toggle error silently reverts state

**File:** `frontend/src/app/notifications/page.tsx`  
**Line:** 123  
**Severity:** 🟡 Medium  
**Impact:** When preference update fails, state reverts but user gets no error message.

**Current:**
```typescript
} catch {
  setPrefs(prefs); // revert on failure
}
```
**Fix:** Show a toast or error message alongside the revert.

---

### 2.5 `ClassSelector.tsx` — Inner catch silently suppresses class info

**File:** `frontend/src/components/rpg/ClassSelector.tsx`  
**Line:** 49  
**Severity:** 🟡 Medium  
**Impact:** `getMyClass()` failure silently sets `myClassInfo = null` — no warning logged.

**Current:**
```typescript
} catch {
  /* no class yet */
}
```
**Fix:**
```typescript
} catch (e) {
  console.warn("Failed to load user class info", e);
}
```

---

## Files to change

**Backend:**
- `backend/app/api/v1/endpoints/disputes.py` — lines 88, 103, 224 (add `await`)

**Frontend:**
- `frontend/src/components/onboarding/OnboardingWizard.tsx` — lines 187, 226
- `frontend/src/components/rpg/AbilityPanel.tsx` — lines 175, 190
- `frontend/src/app/users/page.tsx` — line 79
- `frontend/src/app/profile/dashboard/page.tsx` — line 75
- `frontend/src/components/rpg/WalletPanel.tsx` — line 98
- `frontend/src/app/quests/[id]/page.tsx` — line 448
- `frontend/src/components/home/HomeClientSection.tsx` — line ~543
- `frontend/src/app/profile/page.tsx` — line ~316
- `frontend/src/components/onboarding/OnboardingWizard.tsx` — line 226
- `frontend/src/app/notifications/page.tsx` — line 123
- `frontend/src/components/rpg/ClassSelector.tsx` — line 49

---

## Validation

After all fixes:
1. `cd frontend && npx tsc --noEmit`
2. `cd backend && pytest tests/test_rewards.py tests/test_security.py tests/test_classes.py -q`
3. Check disputes rate limit enforcement via logs
