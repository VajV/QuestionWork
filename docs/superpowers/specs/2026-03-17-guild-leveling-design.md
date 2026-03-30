# Guild Leveling Design

Date: 2026-03-17
Feature: Guild leveling and seasonal guild progression
Source: [docs/ideas/09-guild-leveling.md](docs/ideas/09-guild-leveling.md)

## Goal

Turn guilds from static public groups into season-based progression entities with visible XP growth, tiers, bonuses, and a guild leaderboard.

## Current Reality

- Guild lifecycle already exists in `guilds`, `guild_members`, `guild_activity`, `guild_reward_cards`, `guild_seasonal_rewards`, and guild public marketplace surfaces.
- Quest confirmation already flows through `guild_economy_service.apply_quest_completion_rewards(...)` for both client-confirm and admin force-complete paths.
- Guild public page already renders a progression area, but it currently represents seasonal set completion rather than guild XP tiers.
- Guild member roles already exist in schema and UI as `leader`, `officer`, and `member`.

## Chosen Approach

Implement guild leveling as a seasonal progression layer stored separately from the base `guilds` record.

### Why this approach

- Preserves season boundaries cleanly instead of mutating lifetime fields.
- Reuses the existing quest-completion hook that already updates guild economy.
- Keeps the public guild profile fast by returning cached seasonal progression data.
- Leaves room for future season rollover and historical views without redesigning the guild core schema.

## Seasonal Model

- Guild XP is tracked per `(guild_id, season_code)`.
- The active season is derived in backend code from current UTC date as `YYYY-S1` or `YYYY-S2`.
- Progression is updated on each confirmed quest completion.
- A reconciliation function exists for repair/backfill and future scheduler use, but the primary write path is the quest completion hook.

## Tier Thresholds

- `bronze`: `0+`
- `silver`: `5000+`
- `gold`: `20000+`
- `platinum`: `50000+`

## Tier Bonuses

- `bronze`: `+0% XP`
- `silver`: `+5% XP`
- `gold`: `+10% XP` and guild-exclusive badge eligibility
- `platinum`: `+15% XP` and unique guild title

For this increment, bonuses are exposed in API/UI as derived state. Existing quest XP formulas are not globally rewritten yet.

## Data Model

### New table: `guild_season_progress`

Fields:

- `id`
- `guild_id`
- `season_code`
- `seasonal_xp`
- `current_tier`
- `last_tier_change_at`
- `created_at`
- `updated_at`

Constraints:

- unique `(guild_id, season_code)`
- `seasonal_xp >= 0`
- `current_tier in ('bronze', 'silver', 'gold', 'platinum')`

### Activity history

Extend `guild_activity.event_type` to allow:

- `guild_xp_awarded`
- `guild_tier_promoted`

## Backend Service

Create `backend/app/services/guild_progression_service.py` with:

- `get_current_season_code(now=None)`
- `calculate_guild_xp_delta(xp_reward)`
- `resolve_tier(seasonal_xp)`
- `get_tier_bonuses(tier)`
- `apply_guild_xp_gain(conn, guild_id, xp_gain, source, user_id=None, quest_id=None, occurred_at=None)`
- `build_progression_snapshot(progress_row, members, trophies, seasonal_sets)`
- `recalculate_guild_progress(conn, guild_id, season_code=None)`

## Integration Points

### Quest confirmation

After guild economy rewards are applied, also apply seasonal guild XP gain using the same `xp_reward` signal.

### Admin force-complete

Reuse the same guild economy hook path so progression remains consistent.

### Guild profile API

Extend `GuildProgressionSnapshot` to include:

- `season_code`
- `seasonal_xp`
- `current_tier`
- `next_tier`
- `next_tier_xp`
- `xp_to_next_tier`
- `progress_percent`
- `tier_bonuses`
- `season_rank`

Existing fields for completed sets, claimed rewards, and leaderboard stay intact.

## Frontend Integration

### Guild public page

- Add a guild tier badge.
- Add a progress bar from current XP to next tier.
- Show current seasonal XP, next threshold, and active bonuses.
- Keep member role labels visible in the member list.

### API contract

Extend guild progression types in `frontend/src/lib/api.ts` to match backend payload additions.

## Non-Goals

- No invite/kick/edit permission workflow rewrite in this increment.
- No season archive browser.
- No global XP multiplier application across unrelated systems.
- No standalone scheduler job required for correctness in v1.

## Verification

- Backend service tests for season resolution, tier resolution, and progression updates.
- Marketplace endpoint test for enriched guild progression payload.
- Frontend TypeScript validation after contract/UI changes.