---
name: Create Alembic Migration
description: "Plan and create a safe QuestionWork Alembic migration with reversible upgrade and downgrade steps."
argument-hint: "Describe the schema change"
agent: "Migration Specialist"
---
Create the requested Alembic migration for QuestionWork.

Requirements:
- Prefer additive rollout-safe changes
- Include explicit `upgrade()` and `downgrade()`
- Add indexes or defaults when required for safety
- Note any operational risks or staged rollout concerns
