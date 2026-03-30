# Playwright Audit Review — 2026-03-10

Raw evidence source: [test_output_playwright_audit.json](../../test_output_playwright_audit.json)

This file corrects earlier overstatements in the Playwright audit interpretation. The raw JSON is preserved unchanged; only the conclusions below are revised.

## Summary

- Raw browser run result: `21 passed`, `13 failed`
- Confirmed frontend defects: `3`
- Inconclusive clusters due to audit preconditions / rate limiting: `2`

## Confirmed Defects

### 1. Register page performs navigation during render

Evidence:

- Playwright captured React warning on both client and freelancer registration steps.
- Code path in [frontend/src/app/auth/register/page.tsx](../../frontend/src/app/auth/register/page.tsx#L21) performs `router.push("/profile")` directly during render.

Conclusion:

- This is a real frontend defect.
- The page should redirect from an effect or a guarded render path, not during render.

### 2. Messages page starts auth-required loading without auth bootstrap guard

Evidence:

- Playwright recorded `401 Unauthorized` requests on `/messages` for both client and freelancer steps.
- [frontend/src/app/messages/page.tsx](../../frontend/src/app/messages/page.tsx#L19) immediately calls `getQuestDialogs(...)` in `useEffect`.
- `getQuestDialogs(...)` uses authenticated API access in [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts#L1055).
- Backend endpoint requires auth in [backend/app/api/v1/endpoints/messages.py](../../backend/app/api/v1/endpoints/messages.py#L88).

Conclusion:

- The earlier statement "messages page is broken" was too broad.
- What is confirmed is an auth/bootstrap defect: the page issues protected requests without an explicit readiness/auth guard.
- The audit does **not** prove the page is fully broken for an already stabilized authenticated session.

### 3. Class dashboard handles no-class users inconsistently

Evidence:

- Playwright recorded `400` and `404` diagnostics on `/profile/class`.
- The page starts parallel requests in [frontend/src/app/profile/class/page.tsx](../../frontend/src/app/profile/class/page.tsx#L55): `getMyClass()`, `getPerkTree()`, `getAbilities()`.
- Backend returns `404` for no selected class at [backend/app/api/v1/endpoints/classes.py](../../backend/app/api/v1/endpoints/classes.py#L46).
- Other class endpoints can still return `400` when class state is missing, e.g. perks in [backend/app/api/v1/endpoints/classes.py](../../backend/app/api/v1/endpoints/classes.py#L121).

Conclusion:

- This is a real frontend flow defect.
- The issue is not only that the page redirects on `404`; the page also starts multiple class-dependent requests before the no-class state is resolved.

## Inconclusive / Incorrect Earlier Conclusions

### 4. Admin logs are not proven broken by this audit

Evidence:

- Playwright recorded `429 Too Many Requests` before admin log conclusions were made.
- All admin routes use shared admin rate limiting via [backend/app/api/v1/endpoints/admin.py](../../backend/app/api/v1/endpoints/admin.py#L60).
- The limiter is global per IP/action in [backend/app/core/ratelimit.py](../../backend/app/core/ratelimit.py#L116).

Conclusion:

- The earlier statement that `/admin/logs` is a confirmed product bug was incorrect.
- This audit only proves that the admin scenario hit shared rate limiting under intensive automated navigation.
- `admin logs`, `fund wallet`, and `broadcast` must be re-tested in a cleaner scenario before calling them broken.

### 5. Quest lifecycle after apply is not proven broken by this audit

Evidence:

- Assignment failed with `400 Bad Request` on the quest page.
- Quest assignment performs escrow hold in [backend/app/services/quest_service.py](../../backend/app/services/quest_service.py#L630).
- Hold requires funds and can fail with insufficient funds in [backend/app/services/wallet_service.py](../../backend/app/services/wallet_service.py#L315).
- The audit did **not** successfully complete the admin wallet funding step before attempting assignment.

Conclusion:

- The earlier statement that the lifecycle `assign -> start -> complete -> confirm -> review` is broken was too strong.
- What is actually proven is narrower: the audit failed to satisfy the assignment precondition, so the lifecycle result is inconclusive.
- This flow must be re-run after verified wallet funding, or with pre-seeded balance, before calling it a product defect.

## Corrected Status Matrix

### Confirmed working

- Public home page opens.
- Public quests board opens.
- Public marketplace opens.
- Anonymous access to profile redirects to login.
- Client profile opens.
- Client dashboard opens.
- Client quest journal opens.
- Client notifications open.
- Client can create a quest from UI.
- Freelancer profile opens.
- Freelancer quest journal opens.
- Freelancer quest board opens.
- Freelancer can apply to a quest.
- Freelancer notifications open.
- Admin login works.
- Admin dashboard opens.
- Admin users page opens.
- Admin quests page opens.
- Admin withdrawals page opens.

### Confirmed defective

- Register page render-time redirect warning.
- Messages page auth/bootstrap behavior.
- Class dashboard no-class handling.

### Not yet proven either way

- Admin logs page functional stability under non-rate-limited conditions.
- Admin wallet funding flow.
- Admin broadcast flow.
- Quest lifecycle after assignment with a funded client wallet.

## Corrected Final Conclusion

The previous interpretation should be replaced with this:

- Base navigation, auth entry, profile areas, quest creation, and quest application are working.
- There are **3 confirmed frontend issues**:
  - register render-time redirect warning,
  - messages auth/bootstrap guard issue,
  - class dashboard no-class flow issue.
- There are **2 inconclusive clusters** that require a cleaner follow-up audit:
  - admin routes after shared rate-limit activation,
  - post-apply quest lifecycle without a verified funded client wallet.

## Recommended Re-test Order

1. Fix the 3 confirmed frontend issues.
2. Re-run admin flows with deliberate pacing or isolated sessions to avoid the shared admin limiter.
3. Re-run assignment and full quest lifecycle only after confirming the client wallet has enough balance for escrow hold.