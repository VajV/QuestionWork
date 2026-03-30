# Posting Supply And Conversion Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise marketplace conversion by turning quest posting into a guided workflow and turning freelancer discovery into a comparable, trust-oriented hiring process.

**Architecture:** Build a continuous buyer flow across quest creation, templates, talent discovery, profiles, shortlist, and compare. Prefer additive changes to existing pages and APIs so the system remains coherent with current routes.

**Tech Stack:** Next.js 14 App Router, TypeScript, React, Tailwind, FastAPI, asyncpg, PostgreSQL, Alembic

---

## File Structure
- Modify: `frontend/src/app/quests/create/page.tsx` — guided posting flow.
- Modify: `frontend/src/app/quests/templates/page.tsx` — template-based acceleration.
- Create: `frontend/src/components/quests/QuestCreationWizard.tsx`
- Create: `frontend/src/components/quests/QuestCreationSidebar.tsx`
- Create: `frontend/src/components/quests/QuestBudgetGuidance.tsx`
- Modify: `frontend/src/app/marketplace/page.tsx` — better quality signals, shortlist actions.
- Modify: `frontend/src/app/users/[id]/page.tsx` — richer public proof.
- Modify: `frontend/src/app/users/page.tsx` — improved ranking signals.
- Create: `frontend/src/app/marketplace/compare/page.tsx` — candidate comparison surface.
- Create: `frontend/src/lib/shortlist.ts` or API helpers in `frontend/src/lib/api.ts`
- Modify: `backend/app/models/user.py` and/or new marketplace response models for proof fields.
- Modify: `backend/app/services/marketplace_service.py` or `backend/app/api/v1/endpoints/marketplace.py` if ranking data is currently assembled there.
- Create: `backend/app/services/shortlist_service.py`
- Create: `backend/app/api/v1/endpoints/shortlists.py`
- Create: `backend/app/models/shortlist.py`
- Create: `backend/alembic/versions/<revision>_add_shortlists_and_profile_proof_fields.py`
- Test: `backend/tests/test_marketplace*.py`
- Test: `backend/tests/test_shortlists.py`

---

## Chunk 1: Guided Quest Posting

### Task 1: Turn quest creation into a guided workflow

**Files:**
- Modify: `frontend/src/app/quests/create/page.tsx`
- Create: `frontend/src/components/quests/QuestCreationWizard.tsx`
- Create: `frontend/src/components/quests/QuestCreationSidebar.tsx`
- Create: `frontend/src/components/quests/QuestBudgetGuidance.tsx`

- [ ] **Step 1: Extract the create page into explicit stages**

Stages should be:
- problem framing
- scope and deliverables
- budget and urgency
- talent requirements
- review and publish

- [ ] **Step 2: Add contextual guidance**

Show in-flow help for budget, grade, response expectations, and portfolio requirements.

- [ ] **Step 3: Add progress persistence**

Use either durable local draft storage or existing draft quest mechanics so abandonment can be resumed.

- [ ] **Step 4: Verify happy path manually**

Run: `cd frontend; npm run dev`
Expected: create flow can be completed without layout/runtime regressions.

---

### Task 2: Connect templates directly to guided posting

**Files:**
- Modify: `frontend/src/app/quests/templates/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Optionally modify: `frontend/src/app/quests/create/page.tsx`

- [ ] **Step 1: Add “start from template” entry in quest creation**

The create flow must surface templates early, not only on a separate management page.

- [ ] **Step 2: Add recommended template groups**

Group templates by common buying intent such as MVP, urgent fix, dashboard, backend refactor.

- [ ] **Step 3: Track template-assisted conversion**

Emit analytics events for template viewed, template selected, quest created from template.

- [ ] **Step 4: Verify type-check and build**

Run: `cd frontend; npx tsc --noEmit; npm run build`
Expected: PASS

---

## Chunk 2: Supply Proof And Marketplace Legibility

### Task 3: Expand public freelancer proof surfaces

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/services/review_service.py`, `backend/app/services/quest_service.py`, and/or marketplace aggregation service to expose proof metrics
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/users/[id]/page.tsx`
- Modify: `frontend/src/app/users/page.tsx`

- [ ] **Step 1: Add proof fields to the public contract**

Target fields:
- `avg_rating`
- `review_count`
- `confirmed_quest_count`
- `completion_rate`
- `typical_budget_band`
- `availability_status`
- `response_time_hint`
- `portfolio_links` or `portfolio_summary`

- [ ] **Step 2: Backfill values from existing data where possible**

Prefer computed fields over manual fields first.

- [ ] **Step 3: Render proof above flavor**

Keep RPG identity, but elevate business proof higher on public profiles and user list cards.

- [ ] **Step 4: Add focused backend tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_marketplace*.py tests/test_reviews*.py -q --tb=short`
Expected: PASS

---

### Task 4: Add guided freelancer credibility onboarding

**Files:**
- Modify: `frontend/src/app/auth/register/page.tsx`
- Modify: `frontend/src/app/profile/page.tsx`
- Create: `frontend/src/app/profile/setup/page.tsx`
- Create: `frontend/src/components/profile/FreelancerOnboardingChecklist.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/api/v1/endpoints/users.py` and/or related service layer for onboarding completion fields
- Create: `backend/alembic/versions/<revision>_add_freelancer_onboarding_fields.py`
- Test: `backend/tests/test_user_profile.py`

- [ ] **Step 1: Add onboarding completeness fields**

Track baseline credibility milestones such as bio, skills, portfolio, availability, and first proof item.

- [ ] **Step 2: Route new freelancers into a setup flow**

After registration, freelancers should be guided into profile completion instead of being dropped into a generic profile surface.

- [ ] **Step 3: Add a visible onboarding checklist**

Checklist should explain how to become hireable, not just how to finish profile cosmetics.

- [ ] **Step 4: Verify setup flow manually and with tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_user_profile.py -q --tb=short`
Expected: PASS

---

### Task 5: Make marketplace ranking more transparent and useful

**Files:**
- Modify: `frontend/src/app/marketplace/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `backend/app/api/v1/endpoints/marketplace.py` and/or related service layer

- [ ] **Step 1: Define ranking dimensions**

At minimum include skill relevance, rating, completed work, recency/activity, and guild/solo context where appropriate.

- [ ] **Step 2: Expose selected ranking context in UI**

Examples: “Высокий рейтинг”, “Сильный подтверждённый опыт”, “Быстро отвечает”.

- [ ] **Step 3: Avoid opaque fake precision**

Do not expose raw scoring formulas if they would mislead; expose reasons, not hidden math.

- [ ] **Step 4: Verify marketplace pagination and sorting still work**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS

---

## Chunk 3: Shortlist And Compare

### Task 6: Add shortlist persistence

**Files:**
- Create: `backend/app/models/shortlist.py`
- Create: `backend/app/services/shortlist_service.py`
- Create: `backend/app/api/v1/endpoints/shortlists.py`
- Modify: `backend/app/api/v1/api.py`
- Create: `backend/alembic/versions/<revision>_add_shortlists_and_profile_proof_fields.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/marketplace/page.tsx`
- Modify: `frontend/src/app/users/[id]/page.tsx`
- Test: `backend/tests/test_shortlists.py`

- [ ] **Step 1: Add shortlist table and endpoints**

Support add/list/remove for authenticated clients.

- [ ] **Step 2: Add shortlist CTA on talent rows and profiles**

Shortlist must be visible without needing a separate hidden page first.

- [ ] **Step 3: Add shortlist counter and “review shortlist” path**

Expose current shortlist count in header or relevant client surfaces.

- [ ] **Step 4: Verify backend tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_shortlists.py -v --tb=short`
Expected: PASS

---

### Task 7: Add candidate comparison page

**Files:**
- Create: `frontend/src/app/marketplace/compare/page.tsx`
- Modify: `frontend/src/app/marketplace/page.tsx`
- Modify: `frontend/src/app/users/[id]/page.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Implement compare route consuming shortlisted users**

Allow comparison of 2-4 candidates on price band, proof, rating, skills, and delivery signals.

- [ ] **Step 2: Add navigation into compare flow**

Marketplace and profile surfaces should both feed into compare.

- [ ] **Step 3: Track compare intent**

Emit compare-started and compare-completed events.

- [ ] **Step 4: Verify build**

Run: `cd frontend; npm run build`
Expected: PASS

---

## Chunk 4: Hiring Flow Reinforcement

### Task 8: Add next-best-action modules after posting

**Files:**
- Modify: `frontend/src/app/quests/[id]/page.tsx`
- Modify: `frontend/src/app/quests/create/page.tsx`
- Modify: `frontend/src/app/marketplace/page.tsx`
- Optionally create: `frontend/src/components/marketplace/RecommendedTalentRail.tsx`

- [ ] **Step 1: Add recommended talent after quest creation**

After publish, show matched talent CTA rather than only success confirmation.

- [ ] **Step 2: Add talent suggestions on quest detail**

Keep this lightweight; reuse existing marketplace query params where possible.

- [ ] **Step 3: Add empty-state recovery**

If liquidity is low, route clients to templates, saved shortlist, or lead capture rather than a dead-end list.

- [ ] **Step 4: Verify client journey manually**

Walk: `/for-clients` -> `/quests/create` -> quest publish -> recommendations -> shortlist -> compare.

---

## Done Criteria For This Plan
- [ ] Quest creation is guided and measurable.
- [ ] Templates accelerate first posting.
- [ ] Freelancer proof is legible on public surfaces.
- [ ] New freelancers have a structured path to become hireable quickly.
- [ ] Clients can shortlist and compare candidates.
- [ ] Posted quests drive talent discovery instead of ending in a static confirmation.
- [ ] All listed verification commands pass.

## Commit Suggestions
- `feat: add guided quest creation workflow`
- `feat: add freelancer credibility onboarding`
- `feat: add marketplace shortlist and compare flows`
- `feat: add public freelancer proof signals`
