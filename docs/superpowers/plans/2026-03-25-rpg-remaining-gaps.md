# Remaining RPG Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining unfinished RPG feature work in QuestionWork, with primary focus on finishing equipment artifact mechanics and secondary focus on verification gaps that still block confident production claims.

**Architecture:** Reuse the existing artifact/card inventory pipeline instead of creating a parallel equipment system. Keep artifact ownership in the current reward tables and add a thin equipped-state layer plus profile-facing effects. Preserve existing guild and solo drop logic. Treat production-readiness as a separate verification track from feature implementation.

**Tech Stack:** FastAPI, asyncpg, Alembic, Pydantic, Next.js App Router, TypeScript.

---

## Scope

This plan covers the unfinished parts discovered during repository audit:

1. Plan 06 is only partially implemented.
2. Several RPG features exist in code but are not safe to call production-ready without fresh verification.

This plan does **not** rebuild completed systems such as quest chains, raids, faction alignment, or reputation stats.

## Files

- Modify: `backend/app/models/marketplace.py`
- Modify: `backend/app/services/guild_card_service.py`
- Modify: `backend/app/api/v1/endpoints/users.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/profile/page.tsx`
- Test: `backend/tests/test_guild_card_service.py`
- Test: `backend/tests/test_guild_economy_service.py`
- Create or Modify: `backend/tests/test_users.py`

### Task 1: Lock the equipment contract

**Files:**
- Modify: `backend/app/models/marketplace.py`
- Modify: `frontend/src/lib/api.ts`
- Test: `backend/tests/test_users.py`

- [ ] Add a stable equipped-state contract for `UserArtifact`, for example `is_equipped`, `slot`, and optional `equipped_effect_summary`.
- [ ] Add response models for equip and unequip mutations, for example `ArtifactEquipRequest` and `ArtifactEquipResponse`.
- [ ] Mirror the backend response shape in `frontend/src/lib/api.ts` without introducing frontend-only fields.
- [ ] Add focused tests that serialize the new contract and prove old collection payloads remain backward compatible.

### Task 2: Persist equipped artifacts safely

**Files:**
- Modify: `backend/app/services/guild_card_service.py`
- Modify: `backend/app/api/v1/endpoints/users.py`
- Test: `backend/tests/test_guild_card_service.py`

- [ ] Decide the minimal persistence shape for v1 equipment state.
- [ ] Prefer additive storage on the existing user-owned artifact records if possible; if not, add a dedicated equipped-state relation in a follow-up migration.
- [ ] Implement service helpers to equip one artifact and automatically clear conflicting items in the same slot if slots are introduced.
- [ ] Keep v1 explicitly non-pay-to-win: allow display or mild profile modifiers only.
- [ ] Add regression tests for duplicate equip, wrong owner, unknown artifact id, and idempotent re-equip.

### Task 3: Expose equip and unequip endpoints

**Files:**
- Modify: `backend/app/api/v1/endpoints/users.py`
- Test: `backend/tests/test_users.py`

- [ ] Add authenticated endpoints for equip and unequip actions under the existing user routes.
- [ ] Preserve the current endpoint layering: endpoint -> service helper -> DB update.
- [ ] Apply existing auth and rate-limit patterns for mutating routes.
- [ ] Return the updated artifact cabinet or a narrow equip response so the frontend can refresh deterministically.
- [ ] Add success-path and main validation-failure coverage.

### Task 4: Surface equipped artifacts in profile UI

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/profile/page.tsx`

- [ ] Add typed API helpers for equip and unequip actions through `fetchApi<T>()`.
- [ ] Extend the artifact cabinet panel to distinguish owned vs equipped artifacts.
- [ ] Add explicit loading, error, and disabled states around equip actions.
- [ ] Show mild effect summaries in the UI if the backend returns them.
- [ ] Keep solo card collection and guild trophy displays unchanged.

### Task 5: Decide and implement v1 artifact effects

**Files:**
- Modify: `backend/app/services/guild_card_service.py`
- Modify: `backend/app/models/marketplace.py`
- Modify: `frontend/src/app/profile/page.tsx`
- Test: `backend/tests/test_guild_card_service.py`

- [ ] Choose one restrained ruleset for equipped artifacts in v1.
- [ ] Recommended v1 scope: cosmetic title, accent, or small profile-only metadata bonus.
- [ ] Do **not** add payout, escrow, or core quest-balance bonuses in this pass.
- [ ] Make effect resolution deterministic and testable from card metadata.
- [ ] Add tests that prove effect summaries are stable for all item categories.

### Task 6: Verification and production-readiness closeout

**Files:**
- Test: `backend/tests/test_guild_card_service.py`
- Test: `backend/tests/test_guild_economy_service.py`
- Test: `backend/tests/test_users.py`
- Modify if needed: any file touched by failed verification

- [ ] Run focused backend tests for artifact/equipment behavior.
- [ ] Run `cd frontend && npx tsc --noEmit` after contract changes.
- [ ] Re-run RPG-adjacent regression tests that touch quest confirmation, profile payloads, and solo/guild card drops.
- [ ] Separate feature failures from environment failures such as missing DB-backed services.
- [ ] Do not claim production-readiness until fresh verification output exists for the changed paths.

## Verification

- Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py tests/test_guild_economy_service.py tests/test_users.py -q --tb=short`
- Run: `cd frontend && npx tsc --noEmit`

## Definition of Done

- Artifact inventory supports an explicit equipped state.
- Users can equip and unequip owned artifacts from the profile.
- Equipped artifacts expose a stable API contract and visible UI state.
- Artifact effects remain intentionally mild and do not distort quest economics.
- Fresh verification exists for backend tests and frontend type-checking.