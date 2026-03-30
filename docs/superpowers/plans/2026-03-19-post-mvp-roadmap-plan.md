# QuestionWork — Post-MVP Roadmap Implementation Plan

**Date:** 2026-03-19  
**Spec:** `docs/superpowers/specs/2026-03-19-project-state-and-next-steps-spec.md`  
**Status:** Ready for execution  
**Phases:** 0 → 5+  

---

## Overview

This plan converts the gap analysis from the spec into ordered, actionable tasks.  
Each phase is independently deployable. Earlier phases unblock later ones.

---

## Phase 0 — Security & Infrastructure Hardening
**Goal:** Fix all blocker-level issues before any user-visible work.  
**Duration:** 1 day  

### Task 0.1 — TOTP setup uses IP allowlist (H-01)
- **File:** `backend/app/api/v1/endpoints/auth.py` (TOTP setup route)
- **Action:** Replace `Depends(require_admin)` with `Depends(require_admin_with_ip)`
- **Test:** Call `/auth/totp/setup` from a non-allowed IP → expect 403

### Task 0.2 — Quest budget minimum on update (H-02)
- **File:** `backend/app/models/quest.py` — `QuestUpdate` model
- **Action:** Change `budget: Decimal = Field(None, ge=0)` → `ge=100`
- **Test:** PATCH quest with budget=0 → 422

### Task 0.3 — Lock platform fee at quest creation (H-03)
- **Files:** `backend/alembic/versions/`, `backend/app/models/quest.py`, `backend/app/services/quest_service.py`, `backend/app/services/wallet_service.py`
- **Action:**
  1. Add migration: `ALTER TABLE quests ADD COLUMN platform_fee_percent NUMERIC(5,2) NOT NULL DEFAULT 10`
  2. At quest creation, read `config.PLATFORM_FEE_PERCENT` and store in the row
  3. In `wallet_service.payout_quest()`, read `quest.platform_fee_percent` instead of live config
- **Test:** Change platform fee in config → existing quests still pay out at original rate

### Task 0.4 — Bound custom_xp in QuestCreate (H-04)
- **File:** `backend/app/models/quest.py` — `QuestCreate`
- **Action:** `custom_xp: Optional[int] = Field(None, ge=10, le=500)`
- **Test:** POST quest with custom_xp=99999 → 422

### Task 0.5 — Hide stub classes in API (H-05 quick fix)
- **File:** `backend/app/api/v1/endpoints/classes.py`
- **Action:** Filter `GET /classes/` to return only classes where `is_fully_implemented=True`; mark only `berserk` as true.  
  (Full class implementation deferred to Phase 2.)
- **Test:** GET /classes/ → returns only 1 class

### Task 0.6 — Validate trial expiry on class confirm (H-06)
- **File:** `backend/app/services/class_service.py` (or equivalent)
- **Action:** In `confirm_class()`, check `trial_expires_at > datetime.utcnow()` → raise `ValueError` if expired
- **Test:** Confirm class 25+ hours after trial start → 400

### Task 0.7 — Enforce HTTPS on delivery URL (H-07)
- **File:** `backend/app/models/quest.py` — `QuestComplete` (or wherever delivery_url is validated)
- **Action:** Use `pydantic.HttpUrl` AND add validator: `if url.scheme != 'https': raise ValueError`
- **Test:** POST complete with `http://...` → 422; with `https://...` → 200

### Task 0.8 — Infrastructure secrets
- **Files:** `docker-compose.dev.yml`, `docker-compose.db.yml`, `.env.example`
- **Action:**
  1. Replace hardcoded secrets with `${VAR:?required}` syntax so docker-compose fails fast
  2. Add `.env.example` with placeholder values
  3. Confirm `COOKIE_SECURE` defaults to `True` in `core/config.py`
  4. Document admin IP allowlist setup in README

---

## Phase 1 — Code Quality & Email Pipeline
**Goal:** Eliminate known frontend fragility and wire up email delivery.  
**Duration:** 2–3 days  

### Task 1.1 — Frontend Error Boundaries (M-01)
- **Files:** Complex pages — `/quests/[id]/page.tsx`, `/profile/page.tsx`, `/disputes/[id]/page.tsx`
- **Action:** Wrap each page's async-loaded section in a `<ErrorBoundary fallback={<ErrorCard />}>` component
- **Test:** Force a React render error → error card shown, not white screen

### Task 1.2 — Frontend API retry logic (M-02)
- **File:** `frontend/src/lib/api.ts` — `fetchApi()`
- **Action:** On 429 or 503, retry after `Retry-After` header (or 2s default), max 2 retries
- **Test:** Mock 429 response → function retries and eventually returns data or throws `ApiError`

### Task 1.3 — Fix WalletPanel unmount race (M-03)
- **File:** `frontend/src/components/` wallet panel component
- **Action:** Add `isMounted` ref + abort controller; cancel fetch on unmount
- **Test:** Navigate away from wallet page before load completes → no console warning

### Task 1.4 — Email pipeline wiring
- **Files:** `backend/app/jobs/tasks/email_send.py`, `backend/app/core/config.py`, `backend/app/services/notification_service.py`
- **Action:**
  1. Add SMTP settings to `config.py` (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM)
  2. Implement `email_send` job handler: connect SMTP, render template, send
  3. Create 3 email templates (Jinja2): `review_received.html`, `quest_status_changed.html`, `withdrawal_result.html`
  4. In `notification_service.create_notification()`, when `category=transactional`, also enqueue an email job
- **Test:** Create a review → `email_outbox` row inserted → worker processes it → email sent (log / mock SMTP)

---

## Phase 2 — Character Classes Completion
**Goal:** Implement the 5 remaining character classes so the RPG class system works.  
**Duration:** 3–5 days  

### Task 2.1 — Design class stats & perks
- **Output:** Fill in `backend/app/core/classes.py` (or DB seed) with:
  - **Rogue:** DEX-focused; perks: `stealth_bid` (bid invisibly), `quick_apply` (skip daily limit), `critical_review` (bonus XP on 5★ review)
  - **Alchemist:** INT-focused; perks: `formula_keeper` (save quest variant), `transmute` (convert perk points to XP), `lab_session` (extend quest deadline)
  - **Paladin:** CHA-focused; perks: `aura_of_trust` (boost trust score display), `shield_price` (freeze budget 24h), `divine_mediation` (auto-resolve minor dispute)
  - **Archmage:** INT-focused; perks: `arcane_analysis` (skill gap report), `mana_surge` (double XP on next quest), `time_warp` (roll back application)
  - **Oracle:** balanced; perks: `foresight` (see applicant count before applying), `prophecy` (AI quest difficulty estimate), `revelation` (reveal hidden quest insights)

### Task 2.2 — DB seed / migration for new classes
- **Action:** Add migration inserting the 5 classes with `is_fully_implemented=True`, their perks, and abilities into the `classes`, `perks`, `abilities` tables

### Task 2.3 — Ability executor runtime effects
- **File:** `backend/app/services/class_service.py`
- **Action:** In `activate_ability()`, after deducting action points, dispatch actual effect:
  - Map each `ability.effect_key` → a handler function
  - Handlers: apply XP multiplier to session, extend quest deadline, unlock shortlist slot, etc.
  - Store effect expiry in `user_active_effects` table (new migration)
- **Test:** Activate `mana_surge` → next quest completion grants 2× XP

### Task 2.4 — Remove H-05 stub filter (un-hide classes)
- **Action:** Revert the `is_fully_implemented` filter from Task 0.5 now that all classes are seeded

---

## Phase 3 — Guild Season Logic & Advanced Onboarding
**Goal:** Make guilds feel alive and make onboarding convert new users better.  
**Duration:** 3 days  

### Task 3.1 — Guild season scoring
- **Files:** `backend/app/services/guild_service.py`, `backend/app/jobs/tasks/`
- **Action:**
  1. When a guild member completes a quest, add points to `guild_seasons.score`
  2. Add a scheduled job `finalize_guild_season` that runs monthly: rank guilds by score, award `guild_seasonal_rewards`, reset scores
  3. Expose `GET /marketplace/guilds/{guild_id}/season` → current season score + rank

### Task 3.2 — Guild rank tiers
- **Action:** Define 5 tiers (Iron, Bronze, Silver, Gold, Legendary) by score thresholds in config; apply tier badge to guild on finalization

### Task 3.3 — Advanced onboarding wizard (frontend)
- **File:** `frontend/src/app/onboarding/page.tsx`
- **Action:** Replace single-step form with 4-step wizard:
  1. Role selection (freelancer / client)
  2. Skill / interest picker (for freelancers)
  3. Character class intro carousel + class selection
  4. First quest recommendation / first posting CTA
- **Test:** Complete all 4 steps → `onboarding_completed=true` in DB

---

## Phase 4 — Client Ratings & Skill Verification Badges
**Goal:** Make the reputation system two-sided and add verified skill badges.  
**Duration:** 2 days  

### Task 4.1 — Client ratings
- **Files:** `backend/app/models/review.py`, `backend/app/api/v1/endpoints/reviews.py`, `backend/app/services/review_service.py`
- **Action:**
  1. Add `reviewer_role` field to `quest_reviews` (via migration)
  2. Allow freelancer to submit a review for the client after quest confirms (direction: freelancer → client)
  3. Show client avg rating on `GET /users/{id}` and in quest listings
- **Test:** Freelancer reviews client → client profile shows updated avg rating

### Task 4.2 — Skill verification badges
- **File:** `backend/app/services/badge_service.py`
- **Action:** After every review, check: does reviewee have ≥3 completed quests with a specific skill tag + avg ≥4.5? If yes, auto-award `verified_{skill}` badge (e.g., `verified_python_developer`)
- **Migration:** Seed new badge rows for top-10 skills in badge catalogue
- **Test:** Complete 3 Python quests with 5★ → `verified_python_developer` badge auto-awarded

---

## Phase 5 — Quest Milestones (Staged Payments)
**Goal:** Allow large quests to be split into paid milestones.  
**Duration:** 4–5 days  

### Task 5.1 — Data model
- **Migration:** Add `quest_milestones` table: `id, quest_id, title, amount, due_date, status (pending/released/disputed), released_at`
- Constraint: `SUM(milestones.amount) == quest.budget`

### Task 5.2 — Backend endpoints
```
POST   /quests/{quest_id}/milestones           — create milestone (client, draft quests only)
GET    /quests/{quest_id}/milestones           — list milestones
POST   /quests/{quest_id}/milestones/{id}/release — client releases milestone payment
POST   /quests/{quest_id}/milestones/{id}/dispute — freelancer disputes non-payment
```

### Task 5.3 — Escrow integration
- On milestone release: transfer `milestone.amount` from escrow to freelancer wallet (minus fee), create wallet_transaction row  
- Quest "complete" only allowed when all milestones released

### Task 5.4 — Frontend
- **File:** `frontend/src/app/quests/create/page.tsx` and `quests/[id]/page.tsx`
- **Action:** Add optional milestone section in quest create form; show milestone progress bar on quest detail

---

## Phase 6+ — Future (Post-MVP+1)

These require separate specs before planning:

| Feature | Why a Separate Spec |
|---------|-------------------|
| **WebSocket real-time** | Requires infra decision (Redis pub/sub vs. native WS manager) |
| **Portfolio projects** | Simple but touches public profile contract |
| **Notification digest emails** | Depends on Phase 1 email pipeline shipping first |
| **Public API / Webhooks** | Auth model (API keys) needs dedicated security spec |
| **Admin analytics dashboard** | Requires charting library + data aggregation design |
| **Mobile-responsive audit** | UI-only pass; schedule separately from feature work |

---

## Acceptance Criteria (per phase)

| Phase | Done When |
|-------|-----------|
| 0 | All 7 H-xx tests passing; no hardcoded secrets in docker-compose |
| 1 | Error boundaries in place; fetchApi retries verified; email_outbox rows created on notify |
| 2 | All 6 classes return from GET /classes/; activating an ability has a measurable effect |
| 3 | Guild season finalizes via scheduler job; onboarding wizard 4-step flow works end-to-end |
| 4 | Client avg rating visible on profile; skill verification badge auto-awarded in test scenario |
| 5 | Create quest with 2 milestones; release one → partial payout in wallet; release second → quest auto-confirms |

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Phase 2 (5 classes) scope creep | Start with minimal perk/ability definitions; flesh out effects in Phase 2.3 iteratively |
| Phase 3 guild season query performance | Index `guild_members.guild_id` + `guild_seasons.guild_id`; run EXPLAIN before shipping |
| Phase 5 milestone escrow consistency | Wrap all milestone release in `SELECT FOR UPDATE` + transaction |
| Email pipeline SMTP misconfiguration on prod | Feature-flag behind `ENABLE_EMAILS=true`; default off until SMTP tested |

---

*Input spec: `docs/superpowers/specs/2026-03-19-project-state-and-next-steps-spec.md`*
