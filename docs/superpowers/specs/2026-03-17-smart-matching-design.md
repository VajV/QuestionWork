# Smart Matching Design

Date: 2026-03-17
Feature: Smart matching for freelancers and quests
Source: [docs/ideas/08-smart-matching.md](docs/ideas/08-smart-matching.md)

## Goal

Replace the current client-side heuristic talent suggestions with backend-backed recommendation endpoints that use the real marketplace signals already stored in the platform.

## Current Reality

- Skills live in `quests.skills` and `users.skills` as JSONB-backed arrays.
- Trust score already exists as cached `users.trust_score`.
- User proof fields already expose `grade`, `avg_rating`, `availability_status`, and inferred `typical_budget_band`.
- Quest detail UI already renders a `RecommendedTalentRail`, but it currently fetches marketplace data and re-scores on the client.
- Quest board already exists and is the most natural first place for a personalized quest feed.

## Chosen Approach

Implement a dedicated matching service and expose two read-only recommendation endpoints.

### Why this approach

- Fixes the real architectural gap: ranking belongs on the backend, not in a React component.
- Reuses existing DB fields and avoids any migration.
- Keeps the feature incremental: no background jobs, no embeddings, no search engine.
- Produces explicit score breakdowns that are testable and explainable.

## Scoring Model

All recommendation scores are normalized to `0..1` and combined with weighted scoring.

### Freelancer for quest

- `skill_overlap` weight `0.45`
- `grade_fit` weight `0.20`
- `trust_score` weight `0.15`
- `availability` weight `0.10`
- `budget_fit` weight `0.10`

### Quest for freelancer

- same weights and same normalized dimensions

## Normalization Rules

### Skill overlap

- Normalize skills by trim + lowercase.
- Score = matched_required_skills / total_required_skills.
- If quest has no skills, return neutral `0.0` rather than inflating weak matches.

### Grade fit

- Map grade order: `novice=0`, `junior=1`, `middle=2`, `senior=3`.
- If freelancer grade meets or exceeds required grade: `1.0`.
- If one tier below: `0.5`.
- Otherwise: `0.0`.

### Trust score

- Use cached `users.trust_score`.
- If null, fallback to `0.0`.

### Availability

- Primary signal: active assigned workload inferred from quests.
- `0 active` -> `1.0`
- `1 active` -> `0.6`
- `2+ active` -> `0.25`
- Apply a soft cap using `availability_status`:
  - contains `full`, `busy`, `offline` -> max `0.25`
  - contains `part`, `limited` -> max `0.6`
  - otherwise keep inferred workload score

### Budget fit

- Use quest budget band compared against user `typical_budget_band`.
- Exact same band -> `1.0`
- Adjacent band -> `0.7`
- Two or more bands apart -> `0.35`
- Unknown user band -> neutral `0.5`

## Endpoint Contracts

### `GET /api/v1/quests/{quest_id}/recommended-freelancers`

- Public read endpoint like quest detail.
- Returns top `10` freelancers.
- Excludes non-freelancers and users already assigned to another role mismatch.
- Payload includes compact freelancer card plus:
  - `match_score`
  - `match_breakdown`
  - `matched_skills`

### `GET /api/v1/users/me/recommended-quests`

- Authenticated freelancer-only endpoint.
- Returns top `10` open quests.
- Excludes quests created by the same user.
- Excludes quests already assigned.
- Payload includes quest summary plus:
  - `match_score`
  - `match_breakdown`
  - `matched_skills`

## Frontend Integration

### Quest detail

- Replace `RecommendedTalentRail` client-side scoring with direct call to `GET /quests/{id}/recommended-freelancers`.
- Keep existing visual rail, but enrich with trust score and explicit matched skills.

### Quest board

- Add `Quests for you` panel for authenticated freelancers near the top of the board.
- Use `GET /users/me/recommended-quests`.
- Keep it read-only and non-blocking; main board remains the canonical quest list.

## Non-Goals

- No DB migration.
- No scheduler/backfill.
- No semantic search or ML ranking.
- No write-side automation like auto-invite or auto-apply.

## Verification

- Service tests for score normalization and ranking order.
- Endpoint tests for contract, auth, and role guards.
- Frontend type-check after API contract changes.
