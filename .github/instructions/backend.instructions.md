---
description: "Use when editing FastAPI endpoints, backend services, Pydantic models, wallet logic, XP logic, or asyncpg code in QuestionWork. Covers layering, transactions, rate limits, money safety, and notifications."
name: "QuestionWork Backend"
applyTo: "backend/app/**/*.py"
---
# QuestionWork Backend

- Keep the backend flow strict: endpoint -> service -> database query.
- Do not place SQL in route handlers.
- Use asyncpg parameter placeholders `$1, $2, ...` for all user-controlled values.
- Wrap multi-step mutations in `async with conn.transaction()`.
- Use `SELECT ... FOR UPDATE` before mutating rows that were read for decision-making.
- Mutating endpoints must call `check_rate_limit()`.
- Use `Decimal` plus `ROUND_HALF_UP` for money and fee calculations.
- After granting XP, call `check_level_up()` before returning.
- Emit notifications inside the parent transaction, not after it.
- Preserve the existing `/api/v1` routing structure and register new routers in `app/api/v1/api.py`.
