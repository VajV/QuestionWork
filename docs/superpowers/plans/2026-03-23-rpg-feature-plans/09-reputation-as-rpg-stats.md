# Reputation As RPG Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the feeling of a single opaque reputation score with a multi-stat reputation profile that fits the RPG identity of the platform.

**Architecture:** Use the existing user profile stats, trust score, reviews, and badges as inputs into a richer derived profile. Keep trust score intact for compatibility, but add explainable derived stats such as reliability, craft, influence, and resolve.

**Tech Stack:** FastAPI, Pydantic user models, Next.js profile pages, existing stats panel.

---

## Files

- Modify: `backend/app/models/user.py`
- Modify: `backend/app/core/rewards.py`
- Modify: `backend/app/api/v1/endpoints/users.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/rpg/StatsPanel.tsx`
- Modify: `frontend/src/app/profile/page.tsx`
- Modify: `frontend/src/app/users/[id]/page.tsx`
- Test: `backend/tests/test_users.py`

### Task 1: Define the derived reputation stats

- [ ] Choose 3 to 5 derived RPG reputation stats and define exactly which existing signals feed them.
- [ ] Extend `backend/app/models/user.py` to return these stats separately from raw trust score.
- [ ] Keep formulas explicit and testable so future tuning does not become guesswork.

### Task 2: Calculate stats from existing signals

- [ ] Update relevant reward or aggregation code in `backend/app/core/rewards.py` or user endpoint helpers to compute derived reputation values.
- [ ] Ensure no financial or moderation logic accidentally switches from trust score to derived stats without explicit approval.
- [ ] Add tests for formula stability and edge cases such as low-history users.

### Task 3: Build the visible RPG profile layer

- [ ] Sync the new contract into `frontend/src/lib/api.ts`.
- [ ] Update `frontend/src/components/rpg/StatsPanel.tsx` to distinguish combat-style stats from reputation-style stats.
- [ ] Extend `frontend/src/app/profile/page.tsx` and `frontend/src/app/users/[id]/page.tsx` with an explainable reputation breakdown.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_users.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- User profiles expose multi-stat reputation, not only one score.
- Derived stats are explainable and tested.
- Frontend presents the reputation system as part of the RPG identity.
