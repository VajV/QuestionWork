# Trust Score Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted composite trust score for freelancers, expose it through API and UI, and make it usable for marketplace sorting without introducing N+1 reads or hidden formula drift.

**Architecture:** Implement trust score as a denormalized cache on `users` backed by a dedicated `trust_score_service.py`. Recompute it inside existing parent transactions that already mutate review or quest state, surface it through a dedicated endpoint plus public profile/marketplace payloads, and add a lightweight frontend badge/meter for marketplace rows and public profiles.

**Tech Stack:** FastAPI, asyncpg, PostgreSQL JSONB/Numeric fields, Alembic, Pydantic, Next.js 14 App Router, TypeScript, pytest.

## Locked Semantics

Use this contract for the whole implementation pass. Do not reinterpret these rules during coding.

1. `trust_score` is a normalized value in `[0.0, 1.0]`, persisted on `users.trust_score` as `Numeric(5, 4)`.
2. Final score formula is exactly:

```text
trust_score = (avg_rating * 0.4) + (completion_rate * 0.3) + (on_time_rate * 0.2) + (level_bonus * 0.1)
```

3. `avg_rating` is normalized from the existing 5-point rating scale into `[0.0, 1.0]` by `avg_rating_5 / 5`.
4. `completion_rate = confirmed_quests / accepted_quests`, with `0.0` when `accepted_quests = 0`.
5. `on_time_rate = on_time_confirmed_quests / confirmed_quests`, with `0.0` when `confirmed_quests = 0`.
6. `level_bonus` is derived from user grade and normalized into `[0.0, 1.0]`. Lock the mapping in service tests before wiring DB refresh paths.
7. `accepted_quests` means quests assigned to the freelancer that moved beyond marketplace-open states.
8. `confirmed_quests` means quests with final successful completion status used by current business logic for completed work.
9. `on_time_confirmed_quests` means confirmed quests where delivery timestamp is on or before deadline, using `delivery_submitted_at` first and `completed_at` only as fallback.
10. `trust_score_breakdown` must store both normalized components and the raw counters used to produce them so cache contents are auditable.

---

## Scope Check

This feature is one connected subsystem, not multiple independent projects. The backend service, write-time recomputation hooks, read models, marketplace integration, and frontend display all depend on the same trust score contract and should stay in one implementation plan.

## Baseline Evidence To Gather Before Any Fixes

Before editing code, verify the current repo behavior and write down exact file anchors in the implementation notes or commit messages.

1. Confirm which quest statuses are actually used for assigned, completed, cancelled, and revision flows in `quest_service.py` and any status enums/models.
2. Confirm where marketplace `sort_by` validation lives today so the `trust` option is added at the real boundary instead of guessed.
3. Confirm whether public profile payloads already read from `users.avg_rating` and `users.review_count` directly or from helper queries only.
4. Confirm whether current completion timestamps can be null on confirmed quests and whether `delivery_submitted_at` is always the preferred source for on-time evaluation.
5. Confirm whether any additional write paths besides review creation, quest confirmation, and assigned-work cancellation mutate data that should affect trust score in this pass.
6. Confirm whether there is already a user-column regression test file better suited than `test_admin_service.py`; if not, keep the proposed location.

## File Structure

**Create:** `backend/alembic/versions/<revision>_add_user_trust_score_cache.py`
Purpose: add persisted trust score cache fields to `users`.

**Create:** `backend/app/services/trust_score_service.py`
Purpose: own the formula, breakdown generation, DB aggregate queries, and persisted cache refresh.

**Modify:** `backend/app/db/models.py`
Purpose: add ORM columns for trust score cache.

**Modify:** `backend/app/models/user.py`
Purpose: extend public profile models with trust score fields and optionally typed breakdown response model.

**Modify:** `backend/app/api/v1/endpoints/users.py`
Purpose: add `GET /users/{id}/trust-score` and thread trust score into proof-field payloads.

**Modify:** `backend/app/services/review_service.py`
Purpose: refresh trust score after review creation.

**Modify:** `backend/app/services/quest_service.py`
Purpose: refresh trust score after quest confirmation and assigned-work cancellation.

**Modify:** `backend/app/services/marketplace_service.py`
Purpose: expose `trust_score` in marketplace rows and support `trust` sorting / trust tie-breaker.

**Modify:** `backend/app/models/marketplace.py`
Purpose: extend marketplace DTOs and sort enum/query validation if needed.

**Modify:** `backend/app/api/v1/endpoints/quests.py`
Purpose: accept `sort_by=trust` if marketplace endpoint validation lives here.

**Create:** `backend/tests/test_trust_score_service.py`
Purpose: service-level tests for formula, normalization, and edge cases.

**Modify:** `backend/tests/test_review_service.py`
Purpose: verify trust score refresh after review creation.

**Modify:** `backend/tests/test_quest_service.py`
Purpose: verify trust score refresh after confirm/cancel paths.

**Modify:** `backend/tests/test_user_profile.py`
Purpose: verify public profile trust fields and trust score endpoint serialization.

**Modify:** `backend/tests/test_marketplace_public_proof.py`
Purpose: verify marketplace payload and sorting behavior with trust score.

**Modify:** `frontend/src/lib/api.ts`
Purpose: add trust score types and endpoint helper.

**Create:** `frontend/src/components/rpg/TrustScoreBadge.tsx`
Purpose: compact marketplace-safe trust score visual.

**Create:** `frontend/src/components/rpg/TrustScoreMeter.tsx`
Purpose: richer profile breakdown presentation.

**Modify:** `frontend/src/app/marketplace/page.tsx`
Purpose: display trust badge and add trust sort option.

**Modify:** `frontend/src/app/users/[id]/page.tsx`
Purpose: fetch/display trust breakdown on public profile.

## Chunk 1: Backend Trust Score Cache And Formula

### Task 1: Add Persisted Trust Score Fields To Users

**Files:**
- Create: `backend/alembic/versions/<revision>_add_user_trust_score_cache.py`
- Modify: `backend/app/db/models.py`
- Test: `backend/tests/test_admin_service.py`

- [ ] **Step 1: Write the failing ORM/schema test**

Add assertions next to existing user-column tests that `UserORM` has:

```python
trust_score_column = UserORM.__table__.c.trust_score
assert trust_score_column.type.precision == 5
assert trust_score_column.type.scale == 4
assert "trust_score_breakdown" in UserORM.__table__.c
assert "trust_score_updated_at" in UserORM.__table__.c
```

Also assert JSONB/default expectations at the model level where practical so migration intent is visible in tests.

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_admin_service.py -q -k trust_score`
Expected: FAIL because columns do not exist yet.

- [ ] **Step 3: Add the model columns**

In `backend/app/db/models.py`, add to `UserORM`:

```python
trust_score = Column(Numeric(5, 4), nullable=True)
trust_score_breakdown = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
trust_score_updated_at = Column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Add the Alembic migration**

Migration should:

1. add the three columns;
2. backfill existing rows with empty breakdown default;
3. avoid multi-statement SQL packed into one asyncpg execute;
4. use a concrete revision filename once generated and verify it is the only new head.

After writing the migration, run:

`cd backend; .venv/Scripts/python.exe -m alembic heads`

Expected: exactly one head containing the new trust-score revision.

- [ ] **Step 5: Re-run the targeted test**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_admin_service.py -q -k trust_score`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models.py backend/alembic/versions/*.py backend/tests/test_admin_service.py
git commit -m "feat: add persisted trust score cache fields"
```

### Task 2: Implement Trust Score Service

**Files:**
- Create: `backend/app/services/trust_score_service.py`
- Test: `backend/tests/test_trust_score_service.py`

- [ ] **Step 1: Write the failing service tests**

Cover at least these cases:

```python
def test_calculate_trust_score_full_breakdown():
    breakdown = build_trust_breakdown(
        avg_rating_5=4.8,
        accepted_quests=12,
        confirmed_quests=10,
        on_time_quests=9,
        grade="middle",
    )
    assert breakdown["avg_rating"] == pytest.approx(0.96)
    assert breakdown["completion_rate"] == pytest.approx(10 / 12)
    assert breakdown["on_time_rate"] == pytest.approx(0.9)
    assert breakdown["level_bonus"] == 0.5

def test_calculate_trust_score_handles_zero_denominators():
    score, breakdown = calculate_trust_score(...)
    assert score == 0.0
```

Also add explicit tests for:

1. grade-to-level-bonus mapping for every supported grade;
2. score clamping to `[0.0, 1.0]`;
3. breakdown raw counters preserving integer quest counts;
4. null/absent rating input producing `avg_rating = 0.0`.

- [ ] **Step 2: Run the service tests to verify failure**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_trust_score_service.py -q`
Expected: FAIL because service file does not exist.

- [ ] **Step 3: Implement pure helpers first**

Service should include focused helpers:

1. `normalize_rating(avg_rating_5)`
2. `grade_to_level_bonus(grade)`
3. `build_trust_breakdown(...)`
4. `calculate_trust_score(...)`

Keep formula math in one place and clamp score into `[0.0, 1.0]`.

- [ ] **Step 4: Implement DB-backed refresh/read helpers**

Add:

1. `fetch_trust_inputs(conn, user_id)`
2. `refresh_trust_score(conn, user_id)`
3. `get_cached_trust_score(conn, user_id)`

`fetch_trust_inputs()` should aggregate:

1. rating from `users.avg_rating` or reviews aggregate;
2. accepted quests where `assigned_to = user_id` and `status NOT IN ('draft', 'open')`;
3. confirmed quests where `status = 'confirmed'`;
4. on-time confirmed quests using `deadline`, `delivery_submitted_at`, fallback `completed_at`.

Make the SQL explicit before coding:

1. use `users.avg_rating`, `users.review_count`, and `users.grade` as the primary profile inputs so trust reuses the same cached rating source already exposed elsewhere;
2. compute quest counters in one aggregate query if practical, otherwise two small explicit queries are acceptable;
3. treat null deadlines as not on-time eligible instead of silently counting them as on-time;
4. return a fully shaped dict with raw inputs so service tests can validate query-to-breakdown mapping.

- [ ] **Step 5: Re-run the service tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_trust_score_service.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/trust_score_service.py backend/tests/test_trust_score_service.py
git commit -m "feat: add trust score service"
```

## Chunk 2: Backend API And Write-Path Integration

### Task 3: Surface Trust Score In User Models And Endpoint

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/api/v1/endpoints/users.py`
- Test: `backend/tests/test_user_profile.py`

- [ ] **Step 1: Write the failing endpoint/model tests**

Add tests for:

1. `PublicUserProfile` serializes `trust_score` and `trust_score_updated_at`;
2. `GET /users/{id}/trust-score` returns `user_id`, `trust_score`, `breakdown`, `updated_at`;
3. existing profile endpoint includes `trust_score` in proof payload when available.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_user_profile.py -q -k trust`
Expected: FAIL because fields and endpoint do not exist.

- [ ] **Step 3: Add typed API models**

In `backend/app/models/user.py`, add:

1. `trust_score: Optional[float] = None` to `PublicUserProfile`;
2. `trust_score_updated_at: Optional[datetime] = None`;
3. optional dedicated `TrustScoreBreakdown` and `TrustScoreResponse` models if the endpoint benefits from stricter typing.

- [ ] **Step 4: Extend proof-field fetchers**

Update `_fetch_proof_fields()` and `_fetch_proof_batch()` in `backend/app/api/v1/endpoints/users.py` to select:

```sql
u.trust_score,
u.trust_score_updated_at
```

and merge them into `_build_public_profile_payload()`.

- [ ] **Step 5: Add `GET /users/{id}/trust-score`**

Endpoint should:

1. load the user existence guard;
2. return cached score from `trust_score_service.get_cached_trust_score()`;
3. raise `404` when user does not exist;
4. return a stable breakdown shape even when the score is null or zero.

- [ ] **Step 6: Re-run trust-oriented user tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_user_profile.py -q -k trust`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/user.py backend/app/api/v1/endpoints/users.py backend/tests/test_user_profile.py
git commit -m "feat: expose trust score user endpoints"
```

### Task 4: Recompute Trust Score On Review And Quest Mutations

**Files:**
- Modify: `backend/app/services/review_service.py`
- Modify: `backend/app/services/quest_service.py`
- Modify: `backend/tests/test_review_service.py`
- Modify: `backend/tests/test_quest_service.py`

- [ ] **Step 1: Write failing recomputation tests**

Add tests that patch `trust_score_service.refresh_trust_score` and verify it is awaited:

1. once for `reviewee_id` after review insert;
2. once for assigned freelancer after `confirm_quest_completion()`;
3. once for assigned freelancer after client cancels assigned/in-progress/revision_requested work.

- [ ] **Step 2: Run the targeted tests to verify failure**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_review_service.py tests/test_quest_service.py -q -k trust_score`
Expected: FAIL because refresh hook is not called.

- [ ] **Step 3: Add refresh calls inside parent transactions**

Rules:

1. call `await trust_score_service.refresh_trust_score(conn, reviewee_id)` after `_refresh_user_rating()` in `create_review()`;
2. call `await trust_score_service.refresh_trust_score(conn, quest["assigned_to"])` before leaving the main transaction in `confirm_quest_completion()`;
3. in `cancel_quest()`, only refresh for assigned freelancer when the quest had moved beyond open.

Do not start separate transactions from these services.

- [ ] **Step 4: Re-run the targeted tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_review_service.py tests/test_quest_service.py -q -k trust_score`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/review_service.py backend/app/services/quest_service.py backend/tests/test_review_service.py backend/tests/test_quest_service.py
git commit -m "feat: refresh trust score on review and quest updates"
```

## Chunk 3: Marketplace Ranking And Sorting

### Task 5: Thread Trust Score Through Marketplace Payloads

**Files:**
- Modify: `backend/app/models/marketplace.py`
- Modify: `backend/app/services/marketplace_service.py`
- Modify: `backend/tests/test_marketplace_public_proof.py`

- [ ] **Step 1: Write the failing marketplace tests**

Add assertions that:

1. each `TalentMarketMember` includes `trust_score`;
2. explicit trust sort orders higher trust profiles first;
3. default ranking uses trust score as a tie-breaker without dropping existing rank signals.

- [ ] **Step 2: Run the targeted tests to verify failure**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_marketplace_public_proof.py -q -k trust`
Expected: FAIL because DTO/query/sort do not include trust score.

- [ ] **Step 3: Extend marketplace models and queries**

1. add `trust_score: number | null` in backend DTOs;
2. select `u.trust_score` in the marketplace user query;
3. keep existing `rank_signals` intact;
4. do not recalculate trust in marketplace reads.

- [ ] **Step 4: Add `trust` sorting and default tie-breaker**

Implementation rules:

1. `sort_by=trust` => order by `trust_score DESC NULLS LAST`, then current rank score;
2. default sort stays operationally familiar;
3. if two users have identical current rank score, prefer higher `trust_score`;
4. preserve the existing secondary deterministic ordering after trust tie-breaks so pagination stays stable.

Before editing, locate the exact SQL `ORDER BY` construction and update that branch directly instead of layering a second in-memory sort.

- [ ] **Step 5: Re-run targeted marketplace tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_marketplace_public_proof.py -q -k trust`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/marketplace.py backend/app/services/marketplace_service.py backend/tests/test_marketplace_public_proof.py
git commit -m "feat: add trust score marketplace sorting"
```

## Chunk 4: Frontend Trust Score UI

### Task 6: Add API Types And Helper

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/api.ts` via TypeScript compile

- [ ] **Step 1: Add the failing type usage in UI components**

Prepare UI code that expects:

1. `PublicUserProfile.trust_score`;
2. `TalentMarketMember.trust_score`;
3. `TrustScoreResponse`;
4. `getUserTrustScore(userId)` helper.

- [ ] **Step 2: Run TypeScript to verify failure**

Run: `cd frontend; npx tsc --noEmit`
Expected: FAIL because trust types/helper do not exist.

- [ ] **Step 3: Add the API contract**

In `frontend/src/lib/api.ts`, add:

```ts
export interface TrustScoreBreakdown {
  avg_rating: number;
  completion_rate: number;
  on_time_rate: number;
  level_bonus: number;
  raw: {
    average_rating_5: number;
    accepted_quests: number;
    confirmed_quests: number;
    on_time_quests: number;
    grade: UserGrade;
  };
}

export interface TrustScoreResponse {
  user_id: string;
  trust_score: number;
  breakdown: TrustScoreBreakdown;
  updated_at: string | null;
}
```

and implement `getUserTrustScore(userId)` via `fetchApi`.

- [ ] **Step 4: Re-run TypeScript**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add trust score frontend api types"
```

### Task 7: Add Trust Badge And Meter Components

**Files:**
- Create: `frontend/src/components/rpg/TrustScoreBadge.tsx`
- Create: `frontend/src/components/rpg/TrustScoreMeter.tsx`
- Test: `frontend` typecheck

- [ ] **Step 1: Create the minimal failing UI usage**

Reference both components from marketplace/profile pages before implementation.

- [ ] **Step 2: Run TypeScript to verify failure**

Run: `cd frontend; npx tsc --noEmit`
Expected: FAIL because component files do not exist.

- [ ] **Step 3: Implement compact badge**

`TrustScoreBadge.tsx` should accept:

1. `score?: number | null`
2. `size?: "sm" | "md"`

Behavior:

1. null score => neutral `Новый профиль` state;
2. non-null score => shield/badge with `Math.round(score * 100)`.

- [ ] **Step 4: Implement detailed meter**

`TrustScoreMeter.tsx` should accept full response/breakdown and render:

1. total score;
2. four weighted components;
3. last updated text.

- [ ] **Step 5: Re-run TypeScript**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/rpg/TrustScoreBadge.tsx frontend/src/components/rpg/TrustScoreMeter.tsx
git commit -m "feat: add trust score ui components"
```

### Task 8: Integrate Trust Score Into Marketplace And Public Profile

**Files:**
- Modify: `frontend/src/app/marketplace/page.tsx`
- Modify: `frontend/src/app/users/[id]/page.tsx`
- Test: `frontend` typecheck

- [ ] **Step 1: Write the failing UI integration expectations**

At minimum, ensure the pages reference:

1. trust sort option in marketplace;
2. `TrustScoreBadge` in `MarketplaceMemberRow`;
3. `TrustScoreMeter` in public profile using `getUserTrustScore(userId)`.

- [ ] **Step 2: Run TypeScript to verify failure**

Run: `cd frontend; npx tsc --noEmit`
Expected: FAIL until the pages consume the new API and components correctly.

- [ ] **Step 3: Integrate marketplace**

In `frontend/src/app/marketplace/page.tsx`:

1. add `{ value: "trust", label: "Trust" }` to `SORT_OPTIONS`;
2. render `TrustScoreBadge` near rating/proof chips;
3. pass `sort_by=trust` through existing marketplace fetch flow.

- [ ] **Step 4: Integrate public profile**

In `frontend/src/app/users/[id]/page.tsx`:

1. fetch `getUserTrustScore(userId)` alongside profile load;
2. handle loading/error/empty state separately from profile fetch;
3. render `TrustScoreMeter` in the proof/hero area without breaking existing review list.

- [ ] **Step 5: Re-run TypeScript**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/marketplace/page.tsx frontend/src/app/users/[id]/page.tsx
git commit -m "feat: surface trust score in marketplace and profile"
```

## Chunk 5: Verification And Backfill Safety

### Task 9: Add Regression Coverage And Backfill Entry Point

**Files:**
- Modify: `backend/tests/test_user_profile.py`
- Modify: `backend/tests/test_marketplace_public_proof.py`
- Create or Modify: `backend/scripts/backfill_user_trust_scores.py`

- [ ] **Step 1: Write failing regression/backfill tests**

Cover:

1. profile payload includes trust score after service refresh;
2. marketplace payload includes trust score for multiple users;
3. backfill script iterates users and calls refresh service without opening nested transactions incorrectly.

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_user_profile.py tests/test_marketplace_public_proof.py -q -k trust`
Expected: FAIL because trust fields are not yet fully threaded.

- [ ] **Step 3: Implement the backfill script**

Add a small admin-safe script that:

1. scans users in batches;
2. calls `trust_score_service.refresh_trust_score(conn, user_id)`;
3. logs progress;
4. supports `--dry-run` and `--limit` for safer rollout;
5. can be run once after migration deploy.

- [ ] **Step 4: Re-run backend regression slice**

Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_trust_score_service.py tests/test_review_service.py tests/test_quest_service.py tests/test_user_profile.py tests/test_marketplace_public_proof.py -q`
Expected: PASS.

- [ ] **Step 5: Re-run frontend verification**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/backfill_user_trust_scores.py backend/tests/test_user_profile.py backend/tests/test_marketplace_public_proof.py
git commit -m "feat: finalize trust score verification and backfill"
```

## Final Verification

- [ ] Run: `cd backend; .venv/Scripts/python.exe -m pytest -o addopts='' tests/test_trust_score_service.py tests/test_review_service.py tests/test_quest_service.py tests/test_user_profile.py tests/test_marketplace_public_proof.py -q`
Expected: PASS.

- [ ] Run: `cd frontend; npx tsc --noEmit`
Expected: PASS.

- [ ] Run: `cd backend; .venv/Scripts/python.exe scripts/backfill_user_trust_scores.py --dry-run`
Expected: completes without nested-transaction/runtime errors.

- [ ] Run a targeted marketplace smoke check against seeded users with different trust values.
Expected: explicit `sort_by=trust` returns descending cached trust scores and default sort only uses trust as tie-breaker.

- [ ] Run a targeted profile smoke check for one user with score data and one user without score data.
Expected: both the profile endpoint and `GET /users/{id}/trust-score` return stable payload shapes.

## Notes For Executing-Plans Review

1. Stop if existing marketplace sort validation rejects the new `trust` enum in a different file than expected.
2. Stop if trust score recomputation would need to run from write paths not covered here; do not guess hidden hooks.
3. Keep trust score as a persisted DB cache in this pass; do not add Redis unless a measured performance problem appears.
4. Do not replace default marketplace ranking wholesale in the same pass; use trust as explicit sort and tie-breaker first.

Plan complete and saved to `docs/superpowers/plans/2026-03-17-trust-score-implementation.md`. Ready to execute?