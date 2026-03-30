# Skill Tree Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the perk tree from Berserk-only coverage to a complete, usable multi-class skill tree system.

**Architecture:** Keep the current perk-tree model and unlock flow, add missing perk definitions class-by-class, and expose a frontend-ready tree presentation contract. Do not rebuild unlock mechanics if the existing service already enforces tier and prerequisite rules.

**Tech Stack:** FastAPI, Pydantic, Next.js, TypeScript, existing perk tree service.

---

## Files

- Modify: `backend/app/core/classes.py`
- Modify: `backend/app/services/class_service.py`
- Modify: `backend/app/models/character_class.py`
- Modify: `frontend/src/lib/api.ts`
- Create or Modify: `frontend/src/app/profile/page.tsx`
- Test: `backend/tests/test_phase2_classes.py`

### Task 1: Define missing trees

- [ ] Audit Berserk perk structure in `backend/app/core/classes.py` and copy only the reusable shape, not the content.
- [ ] Add tiered perk definitions for the remaining classes with prerequisites, perk point cost, and effect metadata.
- [ ] Keep IDs and effect payloads predictable so frontend rendering does not need class-specific parsing.
- [ ] Extend test fixtures in `backend/tests/test_phase2_classes.py` to validate every class has a complete tree.

### Task 2: Harden unlock rules

- [ ] Review `unlock_perk()` and related helpers in `backend/app/services/class_service.py` for assumptions that only Berserk exists.
- [ ] Update perk point calculations and prerequisite checks so the service is class-agnostic.
- [ ] Add negative tests for invalid tier unlocks, duplicate unlocks, and wrong-class perk IDs.

### Task 3: Expose the tree in API and UI

- [ ] Ensure `backend/app/models/character_class.py` returns enough information for frontend grouping by tier and perk state.
- [ ] Sync contract changes into `frontend/src/lib/api.ts`.
- [ ] Add a perk-tree section to `frontend/src/app/profile/page.tsx` or a dedicated subcomponent using the existing user class info.
- [ ] Show locked, unlockable, and unlocked states distinctly without requiring backend changes later.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase2_classes.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Every supported class has a complete perk tree.
- Unlock rules work uniformly across classes.
- The frontend can render class-specific trees without ad hoc parsing.
