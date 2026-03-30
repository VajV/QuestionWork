---
name: Sync API Contract
description: "Synchronize QuestionWork backend Pydantic models, frontend API helpers, and shared TypeScript interfaces after a contract change."
argument-hint: "Describe the contract drift or API change"
agent: "agent"
---
Synchronize the backend and frontend API contract for QuestionWork.

Requirements:
- Inspect the backend response model or request model
- Update `frontend/src/lib/api.ts`
- Update shared types in `frontend/src/types/index.ts` when needed
- Fix call sites affected by renamed, removed, or newly required fields
