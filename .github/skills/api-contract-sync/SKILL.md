---
name: api-contract-sync
description: 'Keep QuestionWork backend and frontend contracts aligned. Use when Pydantic models, frontend API functions, or shared TypeScript interfaces change.'
argument-hint: 'Describe the backend/frontend contract change'
---

# API Contract Sync

## When to Use
- Backend response model changed
- Frontend interface drift is suspected
- New endpoint requires frontend API client and shared types

## Procedure
1. Read the relevant backend model definitions.
2. Update `frontend/src/lib/api.ts` request and response interfaces.
3. Update `frontend/src/types/index.ts` when the types are shared across components.
4. Check call sites that depend on renamed or newly required fields.
5. Run backend and frontend validation suitable for the scope.

## Done Criteria
- Backend payload shape and frontend typing match
- No stale field names remain in call sites
- Breaking changes are explicit and controlled
