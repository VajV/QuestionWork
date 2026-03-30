# Co-op Raid Quests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce multi-member raid quests that let groups of users complete complex contracts together under one quest umbrella.

**Architecture:** Extend the existing quest lifecycle with a raid-specific mode and participant model. Preserve current solo quest behavior by adding an explicit quest type and new participation tables instead of overloading current assignee fields.

**Tech Stack:** FastAPI, asyncpg, Alembic, Next.js quest board and detail flows.

---

## Files

- Modify: `backend/app/models/quest.py`
- Modify: `backend/app/services/quest_service.py`
- Modify: `backend/app/api/v1/endpoints/quests.py`
- Create: `backend/alembic/versions/<new_revision>_add_raid_quests.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/quests/page.tsx`
- Modify: `frontend/src/app/quests/[id]/page.tsx`
- Test: `backend/tests/test_quest_service.py`

### Task 1: Add a raid quest data model

- [ ] Extend `backend/app/models/quest.py` with a `quest_type` field and raid participant response shapes.
- [ ] Add additive persistence for raid party membership, party capacity, and role slots.
- [ ] Keep solo quest rows valid without backfill-heavy migration logic.

### Task 2: Implement raid lifecycle service logic

- [ ] Update `backend/app/services/quest_service.py` to create raid quests, join raid quests, assign raid roles, and complete raids.
- [ ] Preserve existing rate-limit and transaction patterns from current quest mutations.
- [ ] Add tests for capacity rules, duplicate joins, role conflicts, and group completion flow.

### Task 3: Build the raid UI loop

- [ ] Extend `frontend/src/lib/api.ts` with raid quest interfaces and mutation helpers.
- [ ] Update `frontend/src/app/quests/page.tsx` to filter or badge raid quests distinctly.
- [ ] Update `frontend/src/app/quests/[id]/page.tsx` to show raid party state, open slots, and join actions.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_quest_service.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Solo quests still behave exactly as before.
- Raid quests support multiple participants and role slots.
- Frontend users can discover and join raid quests.
