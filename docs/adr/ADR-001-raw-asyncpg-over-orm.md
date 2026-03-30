# ADR-001: Raw asyncpg SQL over ORM for data access

**Status:** Accepted  
**Date:** 2026-03-14  
**Context:** QuestionWork backend

## Decision

All runtime database queries use **raw asyncpg parameterized SQL** (`$1, $2, ...`).  
SQLAlchemy ORM models exist **only for Alembic migration metadata** — they are never used at runtime for reads or writes.

## Rationale

- **Performance:** asyncpg with raw SQL is the fastest PostgreSQL driver for Python; no ORM overhead.
- **Explicitness:** Every query is visible, auditable, and tuneable with `EXPLAIN ANALYZE`.
- **Transactions:** `async with conn.transaction()` + `SELECT ... FOR UPDATE` gives precise control.
- **Simplicity:** No need to learn ORM quirks for N+1, eager/lazy loading, session lifecycle.

## Trade-offs

- Queries are more verbose than ORM.
- Schema changes require updating both Alembic migrations **and** raw SQL in services.
- No automatic relationship loading — must join explicitly.

## Consequences

1. **New tables/columns** must be added via Alembic migration **and** corresponding ORM model (for metadata only).
2. **All SQL** must use parameterized queries — never f-strings with user data.
3. **CI guard:** `alembic check` should run on every PR to catch ORM↔migration drift.
4. If the project ever migrates to ORM writes, it would be a large coordinated effort (XL backlog item).

## Compliance

- All service functions in `backend/app/services/` follow this pattern.
- `backend/app/db/models.py` contains ORM models used only by Alembic.
