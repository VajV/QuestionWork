# PvE Training Quests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add non-client training quests so users can progress, learn systems, and earn controlled rewards without depending only on marketplace activity.

**Architecture:** Extend the current quest system with a training-mode branch that uses the same lifecycle where practical but keeps economic and matchmaking side effects constrained. Avoid splitting into a second unrelated quest service.

**Tech Stack:** FastAPI, asyncpg, quest lifecycle service, Next.js quests UI.

---

## Files

- Modify: `backend/app/models/quest.py`
- Modify: `backend/app/services/quest_service.py`
- Modify: `backend/app/core/rewards.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/quests/page.tsx`
- Modify: `frontend/src/app/quests/[id]/page.tsx`
- Test: `backend/tests/test_quest_service.py`

### Task 1: Define training quest rules

- [ ] Add explicit quest-type or mode support for training quests in `backend/app/models/quest.py`.
- [ ] Define reward caps and completion rules in `backend/app/core/rewards.py` so training cannot distort the economy.
- [ ] Document which lifecycle steps differ from paid client quests.

### Task 2: Implement service-level support

- [ ] Extend `backend/app/services/quest_service.py` to create and complete training quests.
- [ ] Ensure training quests bypass client-specific steps like external applicant competition where appropriate.
- [ ] Add tests for reward caps, repeatability, and user eligibility.

### Task 3: Expose training content in frontend quest views

- [ ] Extend `frontend/src/lib/api.ts` for training-quest fields.
- [ ] Update `frontend/src/app/quests/page.tsx` so users can discover training quests separately from marketplace work.
- [ ] Update `frontend/src/app/quests/[id]/page.tsx` to explain training rewards and restrictions clearly.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_quest_service.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Users can run training quests without client dependency.
- Rewards are capped and predictable.
- Training quests feel like RPG content, not fake marketplace listings.
