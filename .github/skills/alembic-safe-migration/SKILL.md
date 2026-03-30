---
name: alembic-safe-migration
description: 'Create safe Alembic migrations for QuestionWork. Use for schema updates, indexes, backfills, downgrade support, and rollout-safe migration planning.'
argument-hint: 'Describe the schema change to implement safely'
---

# Alembic Safe Migration

## When to Use
- Adding columns or tables
- Changing constraints or indexes
- Backfilling production data
- Reviewing migration safety before merge

## Procedure
1. Prefer additive changes and avoid destructive schema operations.
2. Make `upgrade()` and `downgrade()` explicit and reversible.
3. For existing tables, add safe defaults or staged backfills before enforcing non-null constraints.
4. Add indexes where query patterns or foreign keys require them.
5. Validate that application code and schema changes can coexist during rollout.

## Done Criteria
- Migration is reversible
- Rollout is additive or explicitly approved
- Backfill and constraints are safe for existing data
