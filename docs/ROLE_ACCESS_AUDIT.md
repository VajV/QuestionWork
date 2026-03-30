# Role Access Audit — March 2026

## Scope
- Backend route guards under [backend/app/api/v1/endpoints](backend/app/api/v1/endpoints)
- Shared auth dependencies in [backend/app/api/deps.py](backend/app/api/deps.py)
- Frontend route/UI guards under [frontend/src/app](frontend/src/app)

## Source of truth
- Any authenticated user: `require_auth()` in [backend/app/api/deps.py](backend/app/api/deps.py)
- Admin-only endpoints: `require_admin()` / `require_admin_role_only()` in [backend/app/api/deps.py](backend/app/api/deps.py)

## Access matrix

| Feature | Freelancer | Client | Admin | Notes |
|---|---|---|---|---|
| View quest list/details | Yes | Yes | Yes | Public in [backend/app/api/v1/endpoints/quests.py](backend/app/api/v1/endpoints/quests.py) |
| Create contract | No | Yes | Yes | Guarded in [backend/app/api/v1/endpoints/quests.py](backend/app/api/v1/endpoints/quests.py) |
| Apply to quest | Yes | Limited | Limited | Service prevents applying to own quest / invalid quest state |
| Assign freelancer | Owner only | Owner only | Owner only when owner | Service-level permission check |
| Confirm quest completion | No | Owner only | Owner only when owner | Service-level permission check |
| Cancel quest | No | Owner only | Owner only when owner | Service-level permission check |
| View applications | No | Owner only | Owner only when owner | Service-level permission check |
| Wallet balance/transactions/withdraw | Own only | Own only | Own only | Auth-only wallet endpoints |
| Notifications | Own only | Own only | Own only | Auth-only notification endpoints |
| Reviews create/check | Participant only | Participant only | Participant only | Public listing only for received reviews |
| Quest chat | Participant only | Participant only | Participant only | Enforced in message service |
| Templates CRUD | No | Yes | Yes | Owner-scoped in [backend/app/api/v1/endpoints/templates.py](backend/app/api/v1/endpoints/templates.py) |
| Create quest from template | No | Yes | Yes | Same owner scope as template |
| Classes/perks/abilities | Primary role only | Read-limited | Read-limited | Class mutations are blocked for non-freelancers in service layer |
| Admin panel | No | No | Yes | Enforced in backend and [frontend/src/app/admin/layout.tsx](frontend/src/app/admin/layout.tsx) |
| Admin god-mode actions | No | No | Yes | User edit, ban, XP, wallets, badges, classes, perk points |

## Findings

### Fixed during audit
1. Freelancer users still saw the `+ Создать контракт` CTA in the header even though access was denied later.
   - Fixed in [frontend/src/components/layout/Header.tsx](frontend/src/components/layout/Header.tsx)

2. Admin users were displayed as `Фрилансер` on the profile page.
   - Fixed in [frontend/src/app/profile/page.tsx](frontend/src/app/profile/page.tsx)

### Confirmed correct
1. Admin backend endpoints are consistently protected by `require_admin()` except TOTP bootstrap endpoints, which intentionally use `require_admin_role_only()`.
2. Contract creation is now aligned across backend and frontend for `client` + `admin`.
3. Template creation is aligned across backend and frontend for `client` + `admin`.
4. Public read routes are limited to quest discovery and received reviews only.

## Follow-up recommendations
1. Add automated permission tests for `freelancer/client/admin` on quests, templates, classes, wallet, and admin actions.
2. Add a dedicated frontend helper like `canCreateQuest(user)` / `isAdmin(user)` to avoid repeating role checks.
3. Consider whether admins should bypass owner-only quest actions, or whether current “admin can create but not override owner flow” behavior is intentional.