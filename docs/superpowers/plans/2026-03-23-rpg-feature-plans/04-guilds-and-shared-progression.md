# Guilds And Shared Progression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve guilds from marketplace groups into a deeper RPG progression layer with shared milestones, roles, and member contribution loops.

**Architecture:** Build on the existing guild marketplace, economy, and seasonal reward services. Add shared progression states and contribution surfaces rather than replacing the current guild profile model.

**Tech Stack:** FastAPI, asyncpg, Alembic-safe additive schema work, Next.js marketplace pages.

---

## Files

- Modify: `backend/app/services/marketplace_service.py`
- Modify: `backend/app/services/guild_economy_service.py`
- Modify: `backend/app/services/guild_progression_service.py`
- Modify: `backend/app/models/marketplace.py`
- Create: `backend/alembic/versions/<new_revision>_expand_guild_progression.py`
- Modify: `frontend/src/app/marketplace/page.tsx`
- Modify: `frontend/src/app/marketplace/guilds/[slug]/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Test: `backend/tests/test_guild_card_service.py`

### Task 1: Define guild progression states

- [ ] Add explicit guild milestone, contribution, and member-role response fields to `backend/app/models/marketplace.py`.
- [ ] Create additive schema support for any missing tables or columns needed for shared progression.
- [ ] Keep migration rollback-safe and consistent with existing guild schema evolution.

### Task 2: Apply progression logic in services

- [ ] Extend `backend/app/services/guild_progression_service.py` to calculate shared milestone state and unlock thresholds.
- [ ] Update `backend/app/services/guild_economy_service.py` so relevant quest completions contribute to guild progression.
- [ ] Update `backend/app/services/marketplace_service.py` to expose member contribution summaries in guild profile responses.

### Task 3: Surface guild progression in UI

- [ ] Extend `frontend/src/lib/api.ts` types for guild milestones, roles, and contributions.
- [ ] Update `frontend/src/app/marketplace/guilds/[slug]/page.tsx` to show milestone progress and top contributors.
- [ ] Add marketplace entry points in `frontend/src/app/marketplace/page.tsx` so guild browsing highlights progression identity.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Guilds have visible shared progression.
- Quest activity can advance guild state.
- Guild pages show why a guild matters beyond membership count.
