# Legendary Quest Chains Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-step legendary quest chains that connect several quests into a narrative progression with unique rewards.

**Architecture:** Layer quest-chain metadata on top of the existing quest lifecycle instead of replacing individual quests. A chain should track sequence order, completion state, and final rewards while each child quest still uses the standard quest engine.

**Tech Stack:** FastAPI, asyncpg, Alembic, Next.js quest UI, badge or reward services.

---

## Files

- Modify: `backend/app/models/quest.py`
- Modify: `backend/app/services/quest_service.py`
- Modify: `backend/app/services/badge_service.py`
- Create: `backend/alembic/versions/<new_revision>_add_quest_chains.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/quests/page.tsx`
- Modify: `frontend/src/app/quests/[id]/page.tsx`
- Test: `backend/tests/test_quest_service.py`

### Task 1: Model quest chains

- [ ] Add additive schema for quest chains, chain steps, and user chain progress.
- [ ] Extend `backend/app/models/quest.py` so quests can reference optional chain metadata.
- [ ] Define final chain reward fields without coupling them to one reward type only.

### Task 2: Implement chain progression logic

- [ ] Update `backend/app/services/quest_service.py` so completing one quest step can unlock the next step.
- [ ] Hook chain-final rewards into `backend/app/services/badge_service.py` or the relevant reward path.
- [ ] Add tests for ordered unlocks, partial progress, replay rules, and final reward granting.

### Task 3: Render the chain experience in frontend

- [ ] Extend `frontend/src/lib/api.ts` to expose quest chain status on quest responses.
- [ ] Update `frontend/src/app/quests/page.tsx` to badge legendary chains distinctly.
- [ ] Update `frontend/src/app/quests/[id]/page.tsx` to show previous step, current step, next unlock, and final reward.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_quest_service.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Quest chains exist as first-class progression objects.
- Users can see chain progress across multiple quests.
- Final rewards trigger only after the full chain is complete.
