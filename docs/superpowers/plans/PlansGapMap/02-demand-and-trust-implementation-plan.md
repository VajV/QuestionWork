# Demand And Trust Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first client acquisition and trust layer so new buyers can discover QuestionWork, understand the value proposition, and feel safe posting the first quest.

**Architecture:** Keep the RPG shell, but create a parallel client-first narrative across landing and hiring surfaces. Use reusable trust components and first-party lead capture so demand generation is measurable and can scale beyond a single homepage.

The explicit quarter decision is to keep demand capture CRM first-party: store leads, attribution, nurture status, and outbound cadence state in Postgres rather than adding an external CRM dependency during this roadmap.

**Tech Stack:** Next.js 14 App Router, TypeScript, React, Tailwind, FastAPI, asyncpg, PostgreSQL, Alembic

---

## File Structure
- Modify: `frontend/src/app/page.tsx` — sharpen homepage positioning for buyers.
- Modify: `frontend/src/app/layout.tsx` — improve metadata defaults and OG basis.
- Modify: `frontend/src/components/layout/Header.tsx` — link client-first entry points.
- Create: `frontend/src/app/for-clients/page.tsx` — dedicated client acquisition hub.
- Create: `frontend/src/app/hire/[slug]/page.tsx` or a set of fixed use-case pages under `frontend/src/app/hire/...` — demand capture surfaces by service type.
- Create: `frontend/src/components/marketing/ClientTrustGrid.tsx` — reusable trust and process block.
- Create: `frontend/src/components/marketing/ClientProofStrip.tsx` — outcomes, escrow, hiring velocity, and service assurances.
- Create: `frontend/src/components/marketing/LeadCaptureForm.tsx` — pre-registration demand capture.
- Create: `frontend/src/lib/attribution.ts` — UTM/source persistence.
- Create: `backend/app/models/lead.py` — request/response models for lead capture.
- Create: `backend/app/services/lead_service.py` — DB insert/query helpers for leads.
- Create: `backend/app/api/v1/endpoints/leads.py` — lead intake endpoint.
- Modify: `backend/app/api/v1/api.py` — register leads router.
- Create: `backend/alembic/versions/<revision>_add_growth_leads_table.py` — `growth_leads` table.
- Test: `backend/tests/test_leads.py`
- Test: `frontend` type-check and build

---

## Chunk 1: Client-First Narrative

### Task 1: Reposition the homepage for buyer clarity

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/components/layout/Header.tsx`
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Add a buyer-specific CTA lane on the homepage**

Update `frontend/src/app/page.tsx` so the hero and first two sections explicitly answer:
- what a client can hire here
- why this is safer than generic freelance chaos
- what action to take next

- [ ] **Step 2: Add a persistent header path for clients**

Add a top-level route entry in `frontend/src/components/layout/Header.tsx` pointing to `/for-clients`.

- [ ] **Step 3: Tighten metadata**

Replace the generic metadata in `frontend/src/app/layout.tsx` with copy that mentions hiring IT specialists and contract execution, not just RPG branding.

- [ ] **Step 4: Verify type safety**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Verify production build**

Run: `cd frontend; npm run build`
Expected: PASS

---

### Task 2: Build the dedicated client acquisition hub

**Files:**
- Create: `frontend/src/app/for-clients/page.tsx`
- Create: `frontend/src/components/marketing/ClientTrustGrid.tsx`
- Create: `frontend/src/components/marketing/ClientProofStrip.tsx`
- Modify: `frontend/src/app/globals.css` only if new shared styles are truly needed

- [ ] **Step 1: Create the `/for-clients` page**

The page should include:
- buyer pain framing
- hiring process explanation
- escrow/dispute summary
- CTA to post a quest
- CTA to browse talent
- lead capture for not-ready buyers

- [ ] **Step 2: Extract reusable trust blocks**

Create `ClientTrustGrid.tsx` and `ClientProofStrip.tsx` so the same proof layer can appear on homepage, hiring pages, and quest creation later.

- [ ] **Step 3: Link the new hub from existing entry points**

Add links from homepage buttons and key header/footer areas to `/for-clients`.

- [ ] **Step 4: Verify route loads locally**

Run: `cd frontend; npm run dev`
Expected: `/for-clients` renders without runtime errors.

---

## Chunk 2: Client Acquisition Surfaces

### Task 3: Add use-case hiring pages for inbound demand

**Files:**
- Create: `frontend/src/app/hire/fastapi-backend/page.tsx`
- Create: `frontend/src/app/hire/nextjs-dashboard/page.tsx`
- Create: `frontend/src/app/hire/urgent-bugfix/page.tsx`
- Create: `frontend/src/app/hire/mvp-sprint/page.tsx`
- Optionally create: `frontend/src/components/marketing/HireUseCaseTemplate.tsx`

- [ ] **Step 1: Create one reusable structure for use-case pages**

If page structure repeats heavily, introduce `HireUseCaseTemplate.tsx`.

- [ ] **Step 2: Ship at least four real entry pages**

Each page must contain:
- use-case specific headline
- typical outcomes
- expected budget band
- recommended quest template entry
- related talent CTA
- lead capture fallback

- [ ] **Step 3: Cross-link the use-case pages**

Add internal links between `/for-clients`, homepage, and each hiring page.

- [ ] **Step 4: Verify crawlable metadata**

Ensure each page exports page-level metadata with distinct title/description.

---

### Task 4: Add first-party lead capture before registration

**Files:**
- Create: `frontend/src/components/marketing/LeadCaptureForm.tsx`
- Create: `backend/app/models/lead.py`
- Create: `backend/app/services/lead_service.py`
- Create: `backend/app/api/v1/endpoints/leads.py`
- Modify: `backend/app/api/v1/api.py`
- Create: `backend/alembic/versions/<revision>_add_growth_leads_table.py`
- Test: `backend/tests/test_leads.py`

- [ ] **Step 1: Add the database table for demand leads**

Create `growth_leads` with fields for:
- `id`
- `email`
- `company_name`
- `contact_name`
- `use_case`
- `budget_band`
- `message`
- `source`
- `utm_*`
- `created_at`

- [ ] **Step 2: Add typed lead intake endpoint**

Create `POST /api/v1/leads/` with validation and rate limiting.

- [ ] **Step 3: Add frontend form component**

The form should be reusable on `/for-clients` and `/hire/*` pages.

- [ ] **Step 4: Add focused backend tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_leads.py -v --tb=short`
Expected: PASS

- [ ] **Step 5: Run broader regression slice**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_auth*.py tests/test_admin*.py -q --tb=short`
Expected: PASS

---

### Task 5: Add outbound demand nurture for captured leads

**Files:**
- Modify: `backend/app/models/lead.py`
- Modify: `backend/app/services/lead_service.py`
- Create: `backend/app/services/lead_nurture_service.py`
- Create: `backend/app/scripts/process_lead_nurture.py`
- Modify: `backend/alembic/versions/<revision>_add_growth_leads_table.py` or add a follow-up revision for nurture status fields
- Modify: `frontend/src/components/marketing/LeadCaptureForm.tsx` if additional intent fields are needed
- Test: `backend/tests/test_lead_nurture.py`

- [ ] **Step 1: Add nurture state to captured leads**

Track at minimum:
- `status`
- `last_contacted_at`
- `next_contact_at`
- `nurture_stage`
- `converted_user_id` when applicable

- [ ] **Step 2: Create first outbound cadence**

Implement a minimal sequence for leads who submitted interest but did not start registration or quest posting.

- [ ] **Step 3: Add processor script with idempotency**

The processor must skip already-converted or recently-contacted leads.

- [ ] **Step 4: Verify nurture tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_lead_nurture.py -v --tb=short`
Expected: PASS

---

## Chunk 3: Attribution and Proof

### Task 6: Persist acquisition attribution

**Files:**
- Create: `frontend/src/lib/attribution.ts`
- Modify: `frontend/src/components/ui/ClientAppShell.tsx` or nearest app-shell entry point
- Modify: `frontend/src/lib/api.ts` if request headers need attribution metadata
- Modify: `backend/app/api/v1/endpoints/leads.py` and later auth/quest create endpoints to consume attribution

- [ ] **Step 1: Persist UTM/source params in the browser**

Create `attribution.ts` to read `utm_source`, `utm_medium`, `utm_campaign`, `ref`, and first landing path.

- [ ] **Step 2: Attach attribution to lead intake**

Send stored attribution along with the lead payload.

- [ ] **Step 3: Expose a helper for later registration and quest creation flows**

Keep this helper generic so later plans can reuse it without reworking the API surface.

- [ ] **Step 4: Verify no type regressions**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS

---

### Task 7: Replace implied trust with explicit trust proof

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/for-clients/page.tsx`
- Modify: `frontend/src/app/quests/create/page.tsx` in the later phase if dependency is already open
- Optionally modify: `backend/app/services/meta_service.py` and `backend/app/api/v1/endpoints/meta.py` if real metrics are exposed

- [ ] **Step 1: Decide which trust metrics are real today**

Only expose live metrics that already exist or can be computed honestly.

- [ ] **Step 2: Render trust proof components on high-intent pages**

Show process safety, quality filters, and operational clarity on homepage and `/for-clients`.

- [ ] **Step 3: Flag synthetic content for removal**

Do not ship fake counts or fabricated outcomes into production trust surfaces.

- [ ] **Step 4: Verify visual coherence**

Run the frontend locally and manually inspect homepage and `/for-clients` on mobile and desktop.

---

## Done Criteria For This Plan
- [ ] Client can enter through a dedicated hiring path.
- [ ] There are multiple indexable demand-entry pages.
- [ ] Buyer trust is explicit, not only aesthetic.
- [ ] Leads can be captured before full registration.
- [ ] Captured leads can enter a lightweight outbound nurture cadence.
- [ ] Attribution is persisted for future funnel analysis.
- [ ] All backend and frontend verification commands pass.

## Commit Suggestions
- `feat: add client-first acquisition hub`
- `feat: add demand lead capture endpoint`
- `feat: add outbound demand nurture cadence`
- `feat: add hiring use-case landing pages`
