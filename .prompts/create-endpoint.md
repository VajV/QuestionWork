# Prompt: Create New Backend Endpoint

Use this template when adding a new feature that requires a backend API endpoint
and a matching frontend API function.

---

## Context to collect first

Before writing any code, answer these questions:

1. **Resource name** — what domain entity does this operate on? (e.g. `review`, `contract`)
2. **HTTP method** — GET / POST / PATCH / DELETE?
3. **Path** — must start with `/api/v1/`. Use kebab-case. (e.g. `/api/v1/contracts/`)
4. **Auth level** — public / `require_auth` (any logged-in user) / `require_admin`
5. **Mutation?** — if POST/PATCH/DELETE, rate-limit action name and limit/window

---

## Step 1 — Pydantic request/response models

Add to `backend/app/models/<resource>.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class <Resource>Create(BaseModel):
    field_one: str = Field(..., min_length=1, max_length=500)
    field_two: Optional[str] = None

class <Resource>Response(BaseModel):
    id: str
    field_one: str
    field_two: Optional[str]
    created_at: datetime
```

Rules:
- Use `str` for UUIDs (asyncpg returns them as UUID objects — cast with `str(row["id"])`)
- Use `Decimal` for any money field, never `float`
- Keep response models flat — no nested ORM objects

---

## Step 2 — Service function

Create or add to `backend/app/services/<resource>_service.py`:

```python
import asyncpg
from typing import Optional

async def create_<resource>(
    conn: asyncpg.Connection,
    user_id: str,
    field_one: str,
    field_two: Optional[str] = None,
) -> dict:
    async with conn.transaction():
        # If reading before writing, use FOR UPDATE:
        # existing = await conn.fetchrow(
        #     "SELECT * FROM <resources> WHERE id = $1 FOR UPDATE", resource_id
        # )
        row = await conn.fetchrow(
            """
            INSERT INTO <resources> (user_id, field_one, field_two)
            VALUES ($1, $2, $3)
            RETURNING id, user_id, field_one, field_two, created_at
            """,
            user_id, field_one, field_two,
        )
        # If XP is granted anywhere in this flow:
        # await check_level_up(conn, user_id)
        # If a notification should be emitted:
        # await notification_service.create_notification(conn, user_id, "...", "...")
        return dict(row)
```

Rules:
- **Never** put SQL in endpoint handlers
- Always parameterize with `$1`, `$2`, … — never f-strings
- Wrap mutations in `async with conn.transaction()`
- Call `check_level_up()` after any XP grant
- Emit notifications inside the same transaction

---

## Step 3 — Route handler

Create or add to `backend/app/api/v1/endpoints/<resource>.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.security import get_current_user        # → require_auth
# from app.core.security import require_admin         # → admin only
from app.core.ratelimit import check_rate_limit
from app.db.session import get_db_connection
from app.models.<resource> import <Resource>Create, <Resource>Response
from app.services import <resource>_service
import asyncpg

router = APIRouter(prefix="/<resources>", tags=["<resources>"])

@router.post("/", response_model=<Resource>Response, status_code=201)
async def create_<resource>(
    body: <Resource>Create,
    request: Request,
    current_user = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = request.client.host if request.client else "unknown"
    check_rate_limit(ip, action="create_<resource>", limit=10, window_seconds=60)
    try:
        result = await <resource>_service.create_<resource>(
            conn, current_user.id, body.field_one, body.field_two
        )
        return <Resource>Response(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
```

Rules:
- `ValueError` → 400, `PermissionError` → 403
- Rate-limit all POST/PATCH/DELETE handlers
- Use `status_code=201` for creation, `200` for everything else
- Do NOT put business logic in handlers — delegate to service layer

---

## Step 4 — Register the router

Edit `backend/app/api/v1/api.py`:

```python
# Add import:
from app.api.v1.endpoints import <resource>   # noqa: add to existing import line

# Add include call (alphabetical order preferred):
api_router.include_router(<resource>.router)
```

**⚠ This step is the most commonly forgotten.** Verify with:
```bash
cd backend && .venv/Scripts/python.exe -c \
  "from app.main import app; [print(r.path) for r in app.routes if '<resource>' in r.path]"
```

---

## Step 5 — Alembic migration (if new table/column)

```bash
cd backend
.venv/Scripts/python.exe -m alembic revision --autogenerate -m "add_<resources>_table"
# Review the generated file in alembic/versions/ before applying
.venv/Scripts/python.exe -m alembic upgrade head
```

---

## Step 6 — Frontend TypeScript interface

Add to `frontend/src/lib/api.ts`:

```typescript
// ── <Resource> ─────────────────────────────────────────────────────────

export interface <Resource>Create {
  fieldOne: string;
  fieldTwo?: string;
}

export interface <Resource> {
  id: string;
  fieldOne: string;
  fieldTwo?: string;
  createdAt: string;
}

export async function create<Resource>(
  payload: <Resource>Create,
): Promise<<Resource>> {
  return fetchApi<<Resource>>(
    "/<resources>/",
    { method: "POST", body: JSON.stringify(payload) },
    true, // requiresAuth
  );
}
```

Notes:
- JSON keys: camelCase in TS ↔ snake_case in Python (Next.js `fetch` does NOT auto-convert — match whatever the backend returns)
- Catch `ApiError` (NOT `Response`) in components: `catch (err) { const msg = (err as ApiError).detail }`
- Always handle `loading`, `error`, and empty states in the consuming component

---

## Step 7 — Verify end-to-end

```bash
# 1. Backend tests
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --tb=short -k "<resource>"

# 2. TypeScript check
cd frontend && npx tsc --noEmit

# 3. Manual smoke test
curl -X POST http://localhost:8001/api/v1/<resources>/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"fieldOne": "test"}'
```
