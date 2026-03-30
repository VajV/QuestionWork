# Factions And Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing faction display into a player alignment system where user choices contribute to faction identity, rewards, and seasonal outcomes.

**Architecture:** Build on the current world meta faction calculations and add user-level faction affiliation plus contribution mechanics. Keep the current public faction scoreboard as the top-level world view.

**Tech Stack:** FastAPI, asyncpg, world meta service, user profile UI.

---

## Files

- Modify: `backend/app/services/meta_service.py`
- Modify: `backend/app/models/meta.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/api/v1/endpoints/users.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/profile/page.tsx`
- Modify: `frontend/src/components/ui/SeasonFactionRail.tsx`
- Test: `backend/tests/test_meta_service.py`

### Task 1: Add player-level faction alignment

- [ ] Extend `backend/app/models/user.py` with faction affiliation and contribution summary fields.
- [ ] Add faction-alignment data to relevant user endpoints without breaking existing public profile consumers.
- [ ] Define whether alignment is fixed, seasonal, or switchable with penalties.

### Task 2: Connect alignment to world state

- [ ] Update `backend/app/services/meta_service.py` so faction score calculations can include aggregated user alignment contribution.
- [ ] Add tests that prove faction totals remain stable when user alignment data is sparse.
- [ ] Keep the current faction scoreboard additive and backward compatible.

### Task 3: Surface faction identity in frontend

- [ ] Extend `frontend/src/lib/api.ts` for faction alignment on user payloads.
- [ ] Add faction selection or display in `frontend/src/app/profile/page.tsx`.
- [ ] Enhance `frontend/src/components/ui/SeasonFactionRail.tsx` to show the user's faction position relative to global standings.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_meta_service.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Factions are not only decorative world labels.
- Users have a visible alignment relationship to factions.
- Faction standings can react to player activity.
