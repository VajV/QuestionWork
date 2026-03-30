# Differentiated Card Drops For Guild Vs Solo Players Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dual card-drop system where guild members get a higher drop frequency around 10%, while solo players get a lower drop frequency around 5% but access to more valuable card pools.

**Architecture:** Extend the existing guild card-drop pipeline into a generalized player card reward system instead of replacing it. Keep guild drops compatible with the current trophy and seasonal set flow, and add a parallel solo reward branch with its own reward pool, persistence rules, and frontend presentation so solo users still feel progression without joining a guild.

**Tech Stack:** FastAPI, asyncpg, existing guild reward services, Next.js marketplace/profile UI, TypeScript API contracts.

---

## Files

- Modify: `backend/app/services/guild_card_service.py`
- Modify: `backend/app/services/guild_economy_service.py`
- Modify: `backend/app/services/quest_service.py`
- Modify: `backend/app/models/marketplace.py`
- Modify: `backend/app/models/user.py`
- Create: `backend/alembic/versions/<new_revision>_add_solo_player_card_drops.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/profile/page.tsx`
- Modify: `frontend/src/app/marketplace/guilds/[slug]/page.tsx`
- Test: `backend/tests/test_guild_card_service.py`
- Test: `backend/tests/test_guild_economy_service.py`
- Create or Modify: `backend/tests/test_player_card_drops.py`

### Task 1: Split reward design into guild and solo tracks

- [ ] Review the existing reward families and rarity pools in `backend/app/services/guild_card_service.py`.
- [ ] Define two clear drop strategies:
  - guild members: approximately 10% drop chance, existing guild-family oriented cards
  - solo players: approximately 5% drop chance, smaller but richer pool with better rarity floor or more valuable families
- [ ] Keep reward math deterministic and testable, following the current `roll_quest_card_drop(...)` style.
- [ ] Document which cards stay guild-only because they feed seasonal guild sets.

### Task 2: Generalize backend drop calculation

- [ ] Refactor `backend/app/services/guild_card_service.py` so drop calculation accepts player context such as `is_guild_member`, `drop_track`, or similar explicit input.
- [ ] Preserve current guild drop behavior as the default for active guild members.
- [ ] Add a solo-specific reward rolling path that uses a different chance threshold and separate reward pool metadata.
- [ ] Write failing tests in `backend/tests/test_guild_card_service.py` or `backend/tests/test_player_card_drops.py` that prove:
  - guild path uses the higher drop rate
  - solo path uses the lower drop rate
  - solo path draws from better card definitions

### Task 3: Add persistence for solo-owned cards

- [ ] Design additive schema in `backend/alembic/versions/<new_revision>_add_solo_player_card_drops.py` for storing player-owned solo cards without overloading `guild_reward_cards`.
- [ ] Extend `backend/app/models/user.py` or `backend/app/models/marketplace.py` with response shapes for personal card collections.
- [ ] Decide whether solo cards are collectible-only in v1 or can later plug into profile bonuses.
- [ ] Keep migration additive and rollback-safe.

### Task 4: Hook drop logic into quest confirmation flow

- [ ] Review the current confirmation path in `backend/app/services/quest_service.py` and `backend/app/services/guild_economy_service.py`.
- [ ] Preserve the existing guild reward flow for guild members.
- [ ] Add the solo drop branch for users with no active guild membership so confirmed solo completions can still trigger card rewards.
- [ ] Ensure no quest can generate duplicate cards twice for the same reward branch.
- [ ] Add regression tests in `backend/tests/test_guild_economy_service.py` and `backend/tests/test_player_card_drops.py` for both guild and solo completion scenarios.

### Task 5: Expose cards in frontend surfaces

- [ ] Extend `frontend/src/lib/api.ts` with contracts for personal card drops in addition to existing guild trophies.
- [ ] Keep `frontend/src/app/marketplace/guilds/[slug]/page.tsx` focused on guild trophies and seasonal sets.
- [ ] Add a personal card collection section to `frontend/src/app/profile/page.tsx` for solo-owned drops.
- [ ] Make the UI explain the product rule clearly: guild users get more frequent drops; solo users get rarer but stronger cards.

### Task 6: Balance and rollout safeguards

- [ ] Add configuration constants in the backend service layer for the initial rates instead of scattering magic numbers.
- [ ] Start with product defaults close to:
  - guild members: `10%`
  - solo players: `5%`
- [ ] Add tests that lock these defaults so they do not drift silently.
- [ ] Leave space for future admin tuning without requiring another schema rewrite.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py tests/test_guild_economy_service.py tests/test_player_card_drops.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Guild members still receive guild trophy drops and seasonal-set progression.
- Solo players can receive their own card drops after eligible quest confirmation.
- Guild drop chance is higher than solo drop chance.
- Solo reward pool is visibly better than the guild baseline pool.
- Frontend shows guild trophies and solo collections as separate progression systems.