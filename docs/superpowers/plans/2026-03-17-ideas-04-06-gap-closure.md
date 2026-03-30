# Ideas 04 And 06 Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining implementation gaps from `docs/ideas/04-ability-executor.md` and `docs/ideas/06-onboarding-wizard.md` so the codebase matches the promised gameplay and onboarding behavior.

**Architecture:** Finish the work in two isolated chunks. Chunk 1 aligns ability definitions with the intended gameplay contract and wires the missing effects into backend quest/reward flows while preserving the existing ability UI. Chunk 2 adds a minimal first-party avatar upload flow plus step-order and profile-contract updates so onboarding matches the spec without introducing external object storage.

**Deployment note:** The avatar upload flow in this plan is intentionally a local-disk MVP for the current single-workspace setup. Treat object storage or shared persistent volumes as a separate production-hardening follow-up, not part of this gap-closure plan.

**Tech Stack:** FastAPI, asyncpg, SQLAlchemy ORM metadata, Pydantic, Next.js 14 App Router, TypeScript, Framer Motion, pytest.

**Execution decision on 2026-03-17:** Chunk 2 was executed first. Chunk 1 resumed after the domain rules were explicitly approved as: urgent payout bonus is funded by the client above budget, `cancel_quest` applies an XP sanction to the assigned freelancer, and quest deadlines now participate in a dedicated XP-penalty mechanic.

**Implementation update on 2026-03-17:** Chunk 1 is now implemented end-to-end. The path-based activation alias exists, frontend activation uses it, and backend ability configs/UI labels expose `deadline_penalty_reduce`, `cancel_xp_protect`, and `urgent_payout_bonus`. The missing consumers are now wired as follows:
1. `confirm_quest_completion()` applies a new deadline XP penalty for late delivery and reduces that penalty when `alchemist.transmutation` is active.
2. `cancel_quest()` applies an XP sanction to the assigned freelancer on active-contract cancellation unless `paladin.divine_protection` is active.
3. `wallet_service.split_payment()` now supports a client-funded surcharge above the base quest budget, and `rogue.vanish` uses that path for urgent payouts.
4. Regression coverage for `quest_service` and `commission` passes with `pytest -o addopts='' tests/test_quest_service.py tests/test_commission.py -q`.

---

## Scope

This plan intentionally excludes `docs/ideas/01-dispute-resolution.md`, `docs/ideas/02-email-pipeline.md`, `docs/ideas/03-events-system.md`, and `docs/ideas/05-websocket-realtime.md` because the current repo already implements those at the required product level. The remaining gaps are:

1. Ability executor does not yet cover the missing product effects and still exposes a route shape that differs from the idea doc.
2. Onboarding wizard still lacks avatar upload and does not follow the intended step sequence from the idea doc.

### Ability Mapping Contract For This Plan

Use this exact mapping during implementation. Do not improvise new pairings mid-task:

1. `berserk.rage_mode` keeps `xp_all_bonus` and `burnout_immune` as-is.
2. `alchemist.transmutation` gains `deadline_penalty_reduce`.
3. `paladin.divine_protection` gains `cancel_xp_protect`.
4. `rogue.vanish` gains `urgent_payout_bonus`.

If product decides different pairings, update this table first, then update code.

## Baseline Evidence To Gather Before Any Fixes

- [ ] Verify that the current placeholder ability effect keys are dead code before renaming them.
Run: `rg "catalyst_bonus|transmutation_bonus|vanish_bonus|phantom_bonus|champion_bonus|arcane_surge_bonus|vision_bonus" backend/app backend/tests`
Expected: definitions in `backend/app/core/classes.py` plus little or no real consumers outside tests/UI labels.

- [ ] Enumerate the exact quest-service state paths that can consume active ability effects.
Run: `rg "confirm_quest_completion|request_quest_revision|cancel_quest|split_payment\(|refund_hold\(" backend/app/services/quest_service.py`
Expected: confirm, revision, and cancel flows identified before implementation starts.

- [ ] Resolve the Alchemist decision gate before changing ability keys.
Run: `rg "deadline|penalty" backend/app/services/quest_service.py backend/app/core/rewards.py`
Expected: if no real deadline penalty flow exists, stop and either:
1. get product sign-off that this feature requires a new penalty subsystem, or
2. split Alchemist support into a separate follow-up plan.

- [ ] Confirm onboarding wizard state is not persisted client-side today.
Run: `rg "localStorage|sessionStorage" frontend/src/components/onboarding frontend/src/app/onboarding`
Expected: no matches; step reordering is safe without a client-state migration.

- [ ] Confirm uploads are not yet ignored and add that change as part of the avatar task.
Run: `rg "uploads|avatars" .gitignore frontend/.gitignore`
Expected: no existing ignore rule for backend avatar uploads.

## File Structure

### Chunk 1: Ability Executor Completion

**Modify:** `backend/app/core/classes.py`
Purpose: Align ability effect definitions with the product contract and keep one source of truth for effect keys.

**Modify:** `backend/app/services/class_service.py`
Purpose: Aggregate and apply active ability effects for class XP and effect lookup.

**Modify:** `backend/app/services/quest_service.py`
Purpose: Apply ability effects in quest completion and cancellation/revision-sensitive flows.

**Modify:** `backend/app/api/v1/endpoints/classes.py`
Purpose: Add a spec-aligned activation route alias without breaking the current body-based route.

**Modify:** `frontend/src/components/rpg/AbilityPanel.tsx`
Purpose: Keep displayed effect labels synchronized with the backend effect catalog.

**Modify:** `frontend/src/lib/api.ts`
Purpose: Optionally switch the client to the path-param activation route after the alias is in place.

**Modify:** `backend/tests/test_class_service.py`
Purpose: Endpoint/service coverage for activation route behavior.

**Modify:** `backend/tests/test_ability_executor.py`
Purpose: Failing tests for the missing gameplay effects before implementation.

### Chunk 2: Onboarding Wizard Completion

**Modify:** `backend/app/db/models.py`
Purpose: Add persisted avatar field to `users`.

**Modify:** `backend/app/models/user.py`
Purpose: Expose avatar field in private/public profile models.

**Modify:** `backend/app/api/v1/endpoints/users.py`
Purpose: Accept avatar metadata in profile updates and add a dedicated authenticated avatar upload endpoint.

**Modify:** `backend/app/main.py`
Purpose: Mount a static uploads directory for locally-served avatar files.

**Modify:** `.gitignore`
Purpose: Keep generated avatar files out of git.

**Create:** `backend/alembic/versions/<revision>_add_user_avatar_url.py`
Purpose: Persist the `avatar_url` schema change safely.

**Create:** `backend/tests/test_user_avatar_upload.py`
Purpose: Cover avatar upload validation and profile serialization.

**Modify:** `frontend/src/lib/api.ts`
Purpose: Add avatar upload API helper and include avatar field in profile types.

**Modify:** `frontend/src/types/index.ts`
Purpose: Keep shared profile/admin types consistent if needed.

**Modify:** `frontend/src/components/onboarding/OnboardingWizard.tsx`
Purpose: Reorder steps to class → skills → profile/avatar → badge and wire avatar upload.

**Modify:** `frontend/src/app/onboarding/page.tsx`
Purpose: Preserve guard/redirect behavior after wizard state changes.

**Modify:** `frontend/src/app/auth/register/page.tsx`
Purpose: Keep freelancer redirect stable after the onboarding step order change.

## Chunk 1: Ability Executor Completion

### Task 1: Lock Down The Missing Ability Route Contract

**Files:**
- Modify: `backend/app/api/v1/endpoints/classes.py`
- Modify: `backend/tests/test_classes.py`
- Test: `backend/tests/test_classes.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_activate_ability_accepts_path_param_route(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/classes/abilities/rage_mode/activate",
        headers=auth_headers,
    )

    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_classes.py -q`
Expected: FAIL because `/classes/abilities/{ability_id}/activate` is not registered.

- [ ] **Step 3: Write minimal implementation**

Add a second endpoint in `backend/app/api/v1/endpoints/classes.py`:

```python
@router.post("/abilities/{ability_id}/activate", response_model=AbilityActivateResponse)
async def activate_ability_by_path(...):
    async with conn.transaction():
        return await class_service.activate_ability(conn, current_user.id, ability_id)
```

Keep the existing body-based route for backward compatibility.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_classes.py -q`
Expected: PASS with both activation routes supported.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/classes.py backend/tests/test_classes.py
git commit -m "feat: add path-based ability activation route"
```

### Task 2: Align Ability Effect Definitions With Product Spec

**Files:**
- Modify: `backend/app/core/classes.py`
- Modify: `frontend/src/components/rpg/AbilityPanel.tsx`
- Modify: `backend/tests/test_phase2_classes.py`
- Test: `backend/tests/test_phase2_classes.py`

- [ ] **Step 1: Write the failing tests for effect keys**

Add assertions that the concrete active abilities expose the intended gameplay keys:

```python
def test_alchemist_active_ability_has_deadline_penalty_reduce_effect():
    ability = get_ability_config("alchemist", "transmutation")
    assert ability is not None
    assert ability.effects.get("deadline_penalty_reduce") == 0.10
```

```python
def test_paladin_active_ability_has_cancel_xp_protect_effect():
    ability = get_ability_config("paladin", "divine_protection")
    assert ability is not None
    assert ability.effects.get("cancel_xp_protect") is True
```

```python
def test_rogue_active_ability_has_urgent_payout_bonus_effect():
    ability = get_ability_config("rogue", "vanish")
    assert ability is not None
    assert ability.effects.get("urgent_payout_bonus") == 0.10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_phase2_classes.py -q`
Expected: FAIL because current configs still expose placeholder bonus keys instead of product behavior keys.

- [ ] **Step 3: Write minimal implementation**

Update `backend/app/core/classes.py` so active ability configs expose the behavior the product doc promises:

```python
ALCHEMIST_TRANSMUTATION.effects = {"xp_all_bonus": 0.30, "deadline_penalty_reduce": 0.10}
PALADIN_DIVINE_PROTECTION.effects = {"xp_all_bonus": 0.25, "cancel_xp_protect": True}
ROGUE_VANISH.effects = {"xp_all_bonus": 0.35, "urgent_payout_bonus": 0.10}
```

Update `frontend/src/components/rpg/AbilityPanel.tsx` labels to match the actual backend effect keys and remove labels for keys that no longer exist.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_phase2_classes.py -q`
Expected: PASS with effect keys aligned.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/classes.py backend/tests/test_phase2_classes.py frontend/src/components/rpg/AbilityPanel.tsx
git commit -m "feat: align ability effect definitions with product contract"
```

### Task 3: Apply Missing Ability Effects In Backend Quest Flow

**Files:**
- Modify: `backend/app/services/quest_service.py`
- Modify: `backend/app/services/class_service.py`
- Modify: `backend/tests/test_ability_executor.py`
- Test: `backend/tests/test_ability_executor.py`

- [ ] **Step 1: Write the failing tests**

Add three targeted tests:

```python
async def test_deadline_penalty_reduced_by_active_alchemist_ability():
    ...

async def test_cancel_xp_loss_prevented_by_active_paladin_ability():
    ...

async def test_urgent_payout_bonus_applied_for_active_rogue_ability():
    ...
```

The tests should patch `get_active_ability_effects()` and verify the exact reward / payout / XP result changes rather than only checking that the helper was called.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_ability_executor.py -q`
Expected: FAIL because only `xp_all_bonus` and `burnout_immune` are currently applied.

If the baseline decision gate proved that no deadline penalty subsystem exists, stop this task after the failing test and split the Alchemist effect into a separate plan instead of inventing penalty semantics inside this task.

- [ ] **Step 3: Write minimal implementation**

Implement the missing effect consumers in `backend/app/services/quest_service.py` and keep `backend/app/services/class_service.py:get_active_ability_effects()` as the single aggregation point:

```python
if ability_effects.get("deadline_penalty_reduce"):
    penalty_multiplier *= 1.0 - ability_effects["deadline_penalty_reduce"]

if quest_cancelled and ability_effects.get("cancel_xp_protect"):
    xp_penalty = 0

if is_urgent and ability_effects.get("urgent_payout_bonus"):
    gross_amount *= 1.0 + ability_effects["urgent_payout_bonus"]
```

Keep all money math in `Decimal` with quantization rules already used by the repo.
Touch only quest paths verified in the baseline step: `confirm_quest_completion()`, `request_quest_revision()` if it contains deadline-sensitive penalties, and `cancel_quest()` if XP-loss protection is actually enforced there.
Do not implement a brand-new deadline penalty subsystem inside this task unless the decision gate explicitly approved that scope expansion.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_ability_executor.py -q`
Expected: PASS with the three missing effect integrations covered.

- [ ] **Step 5: Run regression checks**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_class_service.py tests/test_quest_service.py -q`
Expected: PASS with no regressions in existing class/quest flows.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/quest_service.py backend/app/services/class_service.py backend/tests/test_ability_executor.py
git commit -m "feat: apply missing active ability effects in quest flow"
```

## Chunk 2: Onboarding Wizard Completion

### Task 4: Add Persisted Avatar Support To User Profiles

**Files:**
- Create: `backend/alembic/versions/<revision>_add_user_avatar_url.py`
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/models/user.py`
- Modify: `frontend/src/lib/api.ts`
- Test: `backend/tests/test_user_profile.py`

- [ ] **Step 1: Write the failing backend profile test**

Add a serialization assertion:

```python
def test_row_to_user_profile_includes_avatar_url():
    row = {..., "avatar_url": "/uploads/avatars/test.png"}
    profile = row_to_user_profile(row)
    assert profile.avatar_url == "/uploads/avatars/test.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_user_profile.py -q`
Expected: FAIL because `avatar_url` is not in the model mapping.

- [ ] **Step 3: Write minimal implementation**

Add `avatar_url` to:

```python
UserORM
UserProfile
PublicUserProfile
row_to_user_profile()
ProfileUpdatePayload
frontend UserProfile/PublicUserProfile types
```

Use a nullable `VARCHAR` column and do not introduce image-processing dependencies.

- [ ] **Step 4: Add the migration before running app code**

Create an Alembic migration that adds a nullable `avatar_url` column to `users` and drops it on downgrade.

Run: `cd backend; .venv/Scripts/alembic.exe revision -m "add user avatar url"`
Expected: new revision file created, then edited manually with `ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_user_profile.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/*.py backend/app/db/models.py backend/app/models/user.py backend/tests/test_user_profile.py frontend/src/lib/api.ts
git commit -m "feat: add avatar field to user profile contract"
```

### Task 5: Add A Minimal Authenticated Avatar Upload Endpoint

**Files:**
- Modify: `.gitignore`
- Modify: `backend/app/api/v1/endpoints/users.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_user_avatar_upload.py`
- Test: `backend/tests/test_user_avatar_upload.py`

- [ ] **Step 1: Write the failing upload tests**

Create `backend/tests/test_user_avatar_upload.py` with cases for:

```python
def test_upload_avatar_rejects_non_image_files(): ...
def test_upload_avatar_returns_public_path_and_updates_user(): ...
def test_upload_avatar_requires_auth(): ...
def test_upload_avatar_rate_limits_requests(): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_user_avatar_upload.py -q`
Expected: FAIL because no upload endpoint exists.

- [ ] **Step 3: Write minimal implementation**

Add an authenticated endpoint:

```python
@router.post("/me/avatar")
async def upload_my_avatar(file: UploadFile = File(...), ...):
    await check_rate_limit(ip, action="avatar_upload", limit=2, window_seconds=3600)
    # validate mime and extension
    # reject files over the chosen byte limit before writing
    # write to backend/uploads/avatars/<user_id>-<uuid>.<ext>
    # store /uploads/avatars/<filename> in users.avatar_url
```

Mount static files in `backend/app/main.py`:

```python
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
```

Cap size conservatively at a documented limit, allow only `.png`, `.jpg`, `.jpeg`, `.webp`, create the upload directory if missing, and use sanitized generated filenames only.

Add `.gitignore` entry:

```gitignore
backend/uploads/
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_user_avatar_upload.py -q`
Expected: PASS.

- [ ] **Step 5: Run related regression checks**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_user_profile.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .gitignore backend/app/api/v1/endpoints/users.py backend/app/main.py backend/tests/test_user_avatar_upload.py
git commit -m "feat: add authenticated avatar upload flow"
```

### Task 6: Reorder Onboarding To Match Product Flow And Wire Avatar Upload

**Files:**
- Modify: `frontend/src/components/onboarding/OnboardingWizard.tsx`
- Modify: `frontend/src/app/onboarding/page.tsx`
- Modify: `frontend/src/app/auth/register/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Test: frontend typecheck only

- [ ] **Step 1: Add a failing verification note for the current mismatch**

Record the expected sequence directly in code comments or task notes before editing:

```text
Expected onboarding order: class -> skills -> profile/avatar -> badge
Current order: skills -> bio -> class -> badge
```

Also note explicitly: current code has no `localStorage` or `sessionStorage` persistence for onboarding state, so this reorder does not need a client migration.

- [ ] **Step 2: Run frontend typecheck to establish baseline**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS before any changes.

- [ ] **Step 3: Write minimal implementation**

Update `OnboardingWizard.tsx` so it:

```tsx
const STEPS = ["class", "skills", "profile", "badge"]
```

and the profile step includes:

```tsx
const formData = new FormData()
formData.append("file", file)
<input type="file" accept="image/png,image/jpeg,image/webp" />
<img src={previewUrl} ... />
await uploadMyAvatar(file)
await updateMyProfile({ bio, skills, availability_status })
```

Keep `skip`, `completeOnboarding()`, and the `/quests` CTA behavior unchanged.

- [ ] **Step 4: Run frontend typecheck to verify it passes**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 5: Smoke-check the onboarding pages manually**

Run the existing app and verify:

```text
1. Freelancer registration still redirects to /onboarding
2. Wizard opens on class step
3. Avatar can be selected and previewed
4. Skip still redirects to /quests
5. Completion still awards badge and shows CTA
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/onboarding/OnboardingWizard.tsx frontend/src/app/onboarding/page.tsx frontend/src/app/auth/register/page.tsx frontend/src/lib/api.ts
git commit -m "feat: complete onboarding wizard flow"
```

## Final Verification

- [ ] Run: `cd backend; .venv/Scripts/alembic.exe upgrade head`
Expected: PASS with `users.avatar_url` present before API verification.

- [ ] Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_classes.py tests/test_class_service.py tests/test_phase2_classes.py tests/test_ability_executor.py tests/test_user_profile.py tests/test_user_avatar_upload.py -q`
Expected: PASS.

- [ ] Run: `cd frontend; npx tsc --noEmit`
Expected: PASS.

- [ ] Optional if machine budget allows: `cd frontend; npm run build`
Expected: PASS, but this repo has a history of heavy Next builds, so treat build memory failures as environment issues unless reproducible after typecheck passes.

## Execution Notes For The Next Skill

Use `superpowers:executing-plans` for review-first execution. The plan is intentionally split into two independent chunks, so stop after Chunk 1 if ability-effect semantics need product clarification before onboarding work begins.

## Debugging Notes For The Next Skill

Use `superpowers:systematic-debugging` before implementation if any of these happen:

1. Ability effect names in `core/classes.py` do not map cleanly onto existing quest-service branches.
2. Avatar upload fails because local static serving or multipart handling differs between dev and production runtime.
3. Existing tests reveal a different cancellation or payout path than the one assumed here.

Plan complete and saved to `docs/superpowers/plans/2026-03-17-ideas-04-06-gap-closure.md`. Ready to execute?