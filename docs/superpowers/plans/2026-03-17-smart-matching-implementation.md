# Smart Matching Implementation Plan

Date: 2026-03-17
Spec: [docs/superpowers/specs/2026-03-17-smart-matching-design.md](docs/superpowers/specs/2026-03-17-smart-matching-design.md)

## Chunk 1: Backend matching domain

- [ ] Create `backend/app/services/matching_service.py`
- [ ] Implement shared skill normalization and weighted scoring helpers
- [ ] Implement `match_freelancers_for_quest(conn, quest_id, limit=10)`
- [ ] Implement `recommend_quests_for_user(conn, user_id, limit=10)`
- [ ] Add response models for recommendation entries and lists
- [ ] Register endpoint handlers in existing routers:
  - `GET /quests/{quest_id}/recommended-freelancers`
  - `GET /users/me/recommended-quests`

Verification:

- [ ] Add focused backend tests for scoring behavior and endpoint responses

## Chunk 2: Frontend contract and UI

- [ ] Extend `frontend/src/lib/api.ts` with recommendation interfaces and fetchers
- [ ] Rework `frontend/src/components/marketplace/RecommendedTalentRail.tsx` to call backend recommendations instead of marketplace search
- [ ] Add a lightweight recommended quests panel to `frontend/src/app/quests/page.tsx`
- [ ] Ensure loading, empty, and error-tolerant states exist for both surfaces

Verification:

- [ ] Run frontend TypeScript check

## Chunk 3: Debugging and validation

- [ ] Run backend matching test slice
- [ ] Run frontend TypeScript validation
- [ ] Review result against the spec and remove any client-side duplicated ranking logic that remains in scope
