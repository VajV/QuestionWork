---
description: "Use when creating or editing Alembic migrations, schema changes, indexes, or backfills for QuestionWork. Covers additive migrations, downgrade support, and safe rollout patterns."
name: "QuestionWork Alembic"
applyTo: "backend/alembic/**/*.py"
---
# QuestionWork Alembic

- Prefer additive migrations. Do not drop columns or tables without explicit approval.
- Every migration must implement both `upgrade()` and `downgrade()`.
- New non-null columns on populated tables need a safe default or staged backfill.
- Add indexes for foreign keys and high-frequency filters.
- Keep data backfills deterministic and idempotent.
- Avoid driver-specific SQL that conflicts with asyncpg unless already used in the codebase.
- Match schema changes with the backend and frontend contract work in the same task when needed.
