---
description: "Use when editing Next.js App Router pages, React components, hooks, or frontend TypeScript in QuestionWork. Covers fetchApi usage, ApiError handling, async UI states, and contract-safe frontend patterns."
name: "QuestionWork Frontend"
applyTo:
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.tsx"
---
# QuestionWork Frontend

- All API calls must go through `fetchApi<T>()` from `frontend/src/lib/api.ts`.
- Do not add raw `fetch()` calls outside the shared API client.
- Catch `ApiError` and surface `(err as ApiError).detail`.
- Do not store access tokens in localStorage. Follow the in-memory token pattern.
- Every async UI path needs explicit loading, error, and empty-state handling.
- Prefer small data-fetching hooks or shared helpers instead of duplicating request logic in pages.
- Preserve App Router conventions and avoid introducing Pages Router patterns.
- Keep frontend types aligned with backend Pydantic response models.
