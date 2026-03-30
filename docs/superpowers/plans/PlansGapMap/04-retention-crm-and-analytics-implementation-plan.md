# Retention CRM And Analytics Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the lifecycle messaging, repeat-hire loops, attribution, and KPI infrastructure needed to turn one-off marketplace activity into repeatable growth.

**Architecture:** Use first-party event logging and lifecycle orchestration on the existing FastAPI/Postgres stack so the team can measure and react without waiting on third-party tooling. The explicit quarter decision is to avoid adding an external CRM product now; instead, QuestionWork will use Postgres-backed lifecycle tables plus a persistent email/notification outbox. Reuse notifications where immediacy is enough; add a persistent campaign/outbox path for growth messages that must survive worker restarts.

**Tech Stack:** FastAPI, asyncpg, PostgreSQL, Alembic, Next.js, TypeScript, React, notification and email services

---

## File Structure
- Create: `backend/app/models/analytics.py`
- Create: `backend/app/services/analytics_service.py`
- Create: `backend/app/api/v1/endpoints/analytics.py`
- Create: `backend/app/models/lifecycle.py`
- Create: `backend/app/services/lifecycle_service.py`
- Create: `backend/app/api/v1/endpoints/lifecycle.py` or extend existing notifications/meta endpoints
- Create: `backend/alembic/versions/<revision>_add_analytics_and_lifecycle_tables.py`
- Modify: `backend/app/api/v1/api.py`
- Modify: `backend/app/services/email_service.py` if a persistent outbox is added here
- Create: `backend/app/services/email_outbox_service.py`
- Create: `backend/app/scripts/process_lifecycle_messages.py` or app startup scheduler integration if operationally accepted
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/analytics.ts`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/auth/register/page.tsx`
- Modify: `frontend/src/app/quests/create/page.tsx`
- Modify: `frontend/src/app/marketplace/page.tsx`
- Modify: `frontend/src/app/users/[id]/page.tsx`
- Modify: `frontend/src/app/notifications/page.tsx`
- Create: `frontend/src/components/growth/RepeatHireCard.tsx`
- Create: `frontend/src/components/growth/SavedSearchForm.tsx`
- Test: `backend/tests/test_analytics.py`
- Test: `backend/tests/test_lifecycle.py`

---

## Chunk 1: Event Instrumentation

### Task 1: Add a first-party event pipeline

**Files:**
- Create: `backend/app/models/analytics.py`
- Create: `backend/app/services/analytics_service.py`
- Create: `backend/app/api/v1/endpoints/analytics.py`
- Modify: `backend/app/api/v1/api.py`
- Create: `backend/alembic/versions/<revision>_add_analytics_and_lifecycle_tables.py`
- Create: `frontend/src/lib/analytics.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create `analytics_events` table**

Fields should include:
- `id`
- `event_name`
- `user_id`
- `session_id`
- `role`
- `source`
- `path`
- `properties_json`
- `created_at`

- [ ] **Step 2: Create typed ingestion endpoint**

Add a low-overhead endpoint or batching interface for frontend event capture.

- [ ] **Step 3: Create the frontend analytics helper**

The helper must support env-based disablement and simple fire-and-forget calls.

- [ ] **Step 4: Instrument the critical funnel surfaces**

At minimum:
- homepage/client hub
- register page
- quest create page
- marketplace page
- profile page
- compare/shortlist actions

- [ ] **Step 5: Verify backend tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_analytics.py -v --tb=short`
Expected: PASS

---

### Task 2: Publish the KPI scorecard

**Files:**
- Modify: `backend/app/services/meta_service.py`
- Modify: `backend/app/api/v1/endpoints/meta.py`
- Optionally create: `frontend/src/app/admin/growth/page.tsx`

- [ ] **Step 1: Add growth KPI aggregates**

Track:
- client landing -> registration
- registration -> first quest
- quest created -> first application
- application -> hire
- hire -> confirmed completion
- confirmed completion -> repeat hire

- [ ] **Step 2: Expose admin-facing reporting surface**

If no dedicated admin growth page is added yet, extend existing admin meta/dashboard surface with a growth section.

- [ ] **Step 3: Verify queries are cheap enough**

Prefer aggregates/materialized logic if raw event scans become expensive.

---

## Chunk 2: Lifecycle Messaging

### Task 3: Add lifecycle outbox and campaign primitives

**Files:**
- Create: `backend/app/models/lifecycle.py`
- Create: `backend/app/services/lifecycle_service.py`
- Create: `backend/app/services/email_outbox_service.py`
- Create: `backend/app/scripts/process_lifecycle_messages.py`
- Create: `backend/app/api/v1/endpoints/lifecycle.py` or admin-only trigger endpoints
- Create: `backend/alembic/versions/<revision>_add_analytics_and_lifecycle_tables.py`

- [ ] **Step 1: Create lifecycle tables**

Add tables for:
- `lifecycle_campaigns`
- `lifecycle_messages`
- `saved_searches` if bundled here
- `email_outbox`

- [ ] **Step 2: Implement message enqueue logic**

Support triggers for:
- incomplete profile
- incomplete quest draft
- stale shortlist
- completed quest without follow-up action
- dormant client after successful delivery
- captured lead without registration or quest posting

- [ ] **Step 3: Add processing script or scheduler hook**

Do not rely on ephemeral in-process background tasks for critical lifecycle sends.

- [ ] **Step 4: Verify lifecycle tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_lifecycle.py -v --tb=short`
Expected: PASS

---

### Task 4: Add notification preferences and saved search basics

**Files:**
- Modify: `backend/app/models/badge_notification.py` or create dedicated preferences model
- Modify: `backend/app/api/v1/endpoints/notifications.py`
- Modify: `backend/app/services/notification_service.py`
- Create: `frontend/src/components/growth/SavedSearchForm.tsx`
- Modify: `frontend/src/app/notifications/page.tsx`
- Modify: `frontend/src/app/marketplace/page.tsx`
- Modify: `frontend/src/app/quests/page.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add notification preference storage**

Users should be able to opt in/out of digest-style and growth-style nudges separately from transactional alerts.

- [ ] **Step 2: Add saved search/create alert flow**

Start with one simple path: save current marketplace or quest filter set.

- [ ] **Step 3: Add digest or alert hooks**

Saved searches must be capable of feeding lifecycle messages later in the quarter.

- [ ] **Step 4: Verify UI and backend contract**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS

---

## Chunk 3: Repeat Hire And Reactivation

### Task 5: Add repeat-hire actions after successful work

**Files:**
- Create: `frontend/src/components/growth/RepeatHireCard.tsx`
- Modify: `frontend/src/app/profile/quests/page.tsx`
- Modify: `frontend/src/app/quests/[id]/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `backend/app/services/quest_service.py` and/or review flow service if follow-up recommendations are generated there

- [ ] **Step 1: Add explicit repeat-hire CTAs**

Support actions such as:
- hire again
- create similar quest
- invite previous freelancer

- [ ] **Step 2: Add post-completion recommendation state**

Show repeat-hire actions immediately after quest confirmation or in the client dashboard/quest history.

- [ ] **Step 3: Track repeat intent and completion**

Emit events for repeat-hire-started and repeat-hire-completed.

- [ ] **Step 4: Verify primary loop manually**

Walk: confirmed quest -> repeat hire CTA -> create similar quest.

---

### Task 6: Add reactivation cadence

**Files:**
- Modify: `backend/app/services/lifecycle_service.py`
- Modify: `backend/app/scripts/process_lifecycle_messages.py`
- Modify: `frontend/src/app/profile/dashboard/page.tsx` if UI reminders are surfaced there

- [ ] **Step 1: Define reactivation windows**

Start with 7-day, 14-day, and 30-day dormant-client reactivation.

- [ ] **Step 2: Add idempotency guards**

Do not send duplicate growth nudges for the same trigger window.

- [ ] **Step 3: Add reporting for reactivation effectiveness**

Track send -> open/click/return where feasible.

- [ ] **Step 4: Verify tests and scheduler**

Run lifecycle tests plus a dry-run execution of the processor.

---

## Done Criteria For This Plan
- [ ] Event instrumentation exists for the full core funnel.
- [ ] KPI reporting is visible to the team.
- [ ] Lifecycle messages are persisted and processable.
- [ ] The CRM approach is explicitly first-party for this quarter.
- [ ] Saved search / alert basics exist.
- [ ] Repeat-hire flows exist on completed work surfaces.
- [ ] Reactivation cadence exists with idempotent delivery.
- [ ] All listed verification commands pass.

## Commit Suggestions
- `feat: add first-party funnel analytics`
- `feat: add lifecycle campaign and outbox pipeline`
- `feat: add repeat hire and reactivation flows`
