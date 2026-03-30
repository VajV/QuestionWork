# Guild Leveling Implementation Plan

Date: 2026-03-17
Spec: [docs/superpowers/specs/2026-03-17-guild-leveling-design.md](docs/superpowers/specs/2026-03-17-guild-leveling-design.md)

## Chunk 1: Backend seasonal progression foundation

- [ ] Add Alembic migration for `guild_season_progress`
- [ ] Extend `guild_activity` event-type constraint for progression events
- [ ] Add ORM model for guild seasonal progression
- [ ] Create `backend/app/services/guild_progression_service.py`
- [ ] Implement season code, tier resolution, bonuses, and progression update helpers

Verification:

- [ ] Add focused service tests for tier logic and XP accumulation

## Chunk 2: Hook progression into guild runtime

- [ ] Call guild progression updates from `guild_economy_service.apply_quest_completion_rewards(...)`
- [ ] Record `guild_xp_awarded` activity on quest-confirm XP gains
- [ ] Record `guild_tier_promoted` activity when a tier changes
- [ ] Extend guild public profile payload with enriched progression snapshot

Verification:

- [ ] Add endpoint/service coverage for guild profile progression payload

## Chunk 3: Frontend guild progression UI

- [ ] Extend guild progression interfaces in `frontend/src/lib/api.ts`
- [ ] Render tier badge, seasonal XP, next-tier rail, and bonus pills on the guild public page
- [ ] Preserve loading/error/empty behavior of the current guild page

Verification:

- [ ] Run frontend TypeScript check

## Chunk 4: Debugging and validation

- [ ] Run targeted backend pytest slice for guild progression and marketplace guild detail
- [ ] Run frontend TypeScript validation
- [ ] Review the guild detail UI and payload against the approved seasonal model