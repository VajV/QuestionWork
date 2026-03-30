# Equipment Artifacts And Cosmetics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current guild reward card system into a broader artifacts and cosmetics layer that players can collect, equip, and display.

**Architecture:** Reuse the existing guild card drop pipeline as the seed inventory system. Expand reward metadata and add profile-display semantics before adding complex equip-stat mechanics.

**Tech Stack:** FastAPI, asyncpg, marketplace reward services, Next.js profile and guild UI.

---

## Files

- Modify: `backend/app/services/guild_card_service.py`
- Modify: `backend/app/services/guild_economy_service.py`
- Modify: `backend/app/models/marketplace.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/marketplace/guilds/[slug]/page.tsx`
- Modify: `frontend/src/app/profile/page.tsx`
- Test: `backend/tests/test_guild_card_service.py`

### Task 1: Expand reward item semantics

- [ ] Review trophy families and seasonal set logic in `backend/app/services/guild_card_service.py`.
- [ ] Add item categories for cosmetic-only, collectible, and equipable artifacts in `backend/app/models/marketplace.py`.
- [ ] Keep the first iteration non-pay-to-win by limiting equip effects to display or mild profile modifiers.

### Task 2: Connect item earning and ownership

- [ ] Update reward awarding in `backend/app/services/guild_economy_service.py` so relevant activity can yield artifacts beyond guild-only contexts where appropriate.
- [ ] Add backend tests for reward family distribution and ownership persistence.
- [ ] Ensure duplicate handling is explicit: stack, upgrade, or convert to another reward.

### Task 3: Render collections and equipped artifacts

- [ ] Sync updated item contracts into `frontend/src/lib/api.ts`.
- [ ] Extend `frontend/src/app/profile/page.tsx` with a visible artifact/cosmetic cabinet.
- [ ] Update `frontend/src/app/marketplace/guilds/[slug]/page.tsx` so earned sets and rarity tiers remain visible in guild context.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Rewards are modeled as collectible RPG items.
- Players can see owned artifacts and cosmetics.
- Existing guild seasonal rewards keep working.
