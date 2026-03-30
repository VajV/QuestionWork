---
description: "Use when changing backend response models, frontend API functions, or shared TypeScript interfaces in QuestionWork. Covers Pydantic to TypeScript contract sync and breaking-change control."
name: "QuestionWork API Contract"
applyTo:
  - "backend/app/models/**/*.py"
  - "frontend/src/lib/api.ts"
  - "frontend/src/types/**/*.ts"
---
# QuestionWork API Contract

- Treat backend Pydantic models and frontend interfaces as one contract.
- When a backend response shape changes, update `frontend/src/lib/api.ts` and `frontend/src/types/index.ts` in the same task.
- Do not silently rename or remove public fields.
- If a change is breaking, document it in the PR or spec and update all call sites before merging.
- Keep field names consistent with the API payloads instead of adapting them ad hoc in components.
