# Seasonal Lore And World Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing world meta snapshot into a seasonal world-state system with map regions, lore beats, and clearer player-facing progression.

**Architecture:** Extend the current meta service and world response models instead of adding a parallel seasonal subsystem. Frontend should consume a richer world payload via the existing world meta context and render regions, headlines, and progress states from one source of truth.

**Tech Stack:** FastAPI, asyncpg, Pydantic, React context, Next.js UI components.

---

## Files

- Modify: `backend/app/services/meta_service.py`
- Modify: `backend/app/models/meta.py`
- Modify: `backend/app/api/v1/endpoints/meta.py`
- Modify: `frontend/src/context/WorldMetaContext.tsx`
- Modify: `frontend/src/components/ui/SeasonFactionRail.tsx`
- Modify: `frontend/src/components/ui/WorldPanel.tsx`
- Test: `backend/tests/test_meta_service.py`

### Task 1: Expand the seasonal domain model

- [ ] Add region and lore-beat structures to `backend/app/models/meta.py`.
- [ ] Update `backend/app/services/meta_service.py` to produce map-ready seasonal data from current faction, trend, and quest activity signals.
- [ ] Keep the payload additive so existing consumers do not break.

### Task 2: Stabilize the API contract

- [ ] Confirm `backend/app/api/v1/endpoints/meta.py` returns the expanded response model without changing the endpoint shape.
- [ ] Add tests for season stage transitions, region progress fields, and headline generation.
- [ ] Verify low-activity scenarios still return a complete, non-empty world payload.

### Task 3: Build the map-driven UI

- [ ] Extend `frontend/src/context/WorldMetaContext.tsx` to store the richer payload and preserve loading/error handling.
- [ ] Update `frontend/src/components/ui/WorldPanel.tsx` to show regions, active season chapter, and next unlock.
- [ ] Keep `frontend/src/components/ui/SeasonFactionRail.tsx` focused on faction competition while linking it visually to seasonal state.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_meta_service.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- World meta includes map-ready regions and season narrative data.
- Existing `/meta/world` consumers still work.
- Frontend shows a living seasonal map instead of only metrics.
