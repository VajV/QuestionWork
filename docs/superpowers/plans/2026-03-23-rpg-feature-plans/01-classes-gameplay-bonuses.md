# Classes With Gameplay Bonuses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make character classes materially affect quest matching, XP flow, and visible profile benefits instead of being mostly profile metadata.

**Architecture:** Extend the existing class registry in backend core definitions, apply class effects inside service-layer progression and quest reward hooks, and surface the resulting bonus explanation in frontend profile and quest views. Reuse the current class engine and avoid inventing a second rules system.

**Tech Stack:** FastAPI, asyncpg, Pydantic, Next.js App Router, TypeScript, existing class engine.

---

## Files

- Modify: `backend/app/core/classes.py`
- Modify: `backend/app/services/class_service.py`
- Modify: `backend/app/services/quest_service.py`
- Modify: `backend/app/models/character_class.py`
- Modify: `frontend/src/lib/classEngine.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/profile/page.tsx`
- Modify: `frontend/src/app/quests/[id]/page.tsx`
- Test: `backend/tests/test_classes.py`
- Test: `backend/tests/test_phase2_classes.py`

### Task 1: Lock the class bonus contract

- [ ] Review current bonus definitions in `backend/app/core/classes.py` and list which bonuses are already real versus decorative.
- [ ] Define one primary gameplay bonus and one secondary passive for each shipped class without adding net-new persistence yet.
- [ ] Extend `backend/app/models/character_class.py` so API responses can explain active bonuses in a stable shape.
- [ ] Add or update backend tests in `backend/tests/test_classes.py` for the serialized bonus contract.

### Task 2: Apply bonuses in backend progression hooks

- [ ] Update `backend/app/services/class_service.py` to calculate resolved class modifiers from the registry instead of hard-coded special cases.
- [ ] Integrate class-aware adjustments into the reward path in `backend/app/services/quest_service.py` only where existing quest completion already grants XP or related benefits.
- [ ] Verify every XP mutation still routes through existing level-up logic after modifiers are applied.
- [ ] Add regression coverage in `backend/tests/test_phase2_classes.py` for per-class bonus execution.

### Task 3: Surface bonuses in the frontend

- [ ] Update `frontend/src/lib/classEngine.ts` to mirror the backend contract rather than invent frontend-only bonus logic.
- [ ] Extend `frontend/src/lib/api.ts` types for resolved class bonuses and profile rendering.
- [ ] Show active class bonuses in `frontend/src/app/profile/page.tsx` and quest impact hints in `frontend/src/app/quests/[id]/page.tsx`.
- [ ] Run `cd frontend && npx tsc --noEmit` and confirm types remain clean.

### Task 4: Validate the user-facing loop

- [ ] Test class selection, quest completion, and profile refresh using the existing classes endpoints.
- [ ] Confirm the same class bonus values are visible in backend response payloads and frontend UI.
- [ ] Document any classes still intentionally placeholder so tomorrow's work does not over-scope.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_classes.py tests/test_phase2_classes.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Every shipped class has explicit gameplay bonuses.
- Bonuses affect real backend behavior, not only labels.
- Frontend explains the active class effects to the user.
