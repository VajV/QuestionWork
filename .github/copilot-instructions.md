# GitHub Copilot Instructions — QuestionWork

## Project Overview
QuestionWork is an IT freelance marketplace with RPG gamification.
- **Backend**: FastAPI (Python 3.12) + asyncpg + PostgreSQL + Redis
- **Frontend**: Next.js 14 App Router + TypeScript + Tailwind CSS + Framer Motion
- **Concept**: Freelancers take "quests", earn XP, level up through grades (Novice → Junior → Middle → Senior), choose character classes

## Repository Layout
```
QuestionWork/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   ← FastAPI route handlers
│   │   ├── core/               ← security, rewards, config, classes
│   │   ├── db/                 ← asyncpg session/pool
│   │   ├── models/             ← Pydantic models
│   │   ├── schemas/            ← DB-layer schemas
│   │   └── services/           ← business logic layer
│   ├── alembic/versions/       ← DB migrations
│   └── tests/                  ← pytest test suite
└── frontend/
    └── src/
        ├── app/                ← Next.js App Router pages
        ├── components/         ← UI, RPG, layout, admin components
        ├── context/            ← AuthContext
        ├── hooks/              ← custom React hooks
        ├── lib/                ← api.ts (centralized API client)
        └── types/              ← TypeScript interfaces
```

## Architecture Rules

### Backend
1. **Routing**: All endpoints live under `/api/v1/`. Add new routers in `app/api/v1/api.py` — import the module AND call `api_router.include_router(...)`.
2. **Layers**: HTTP handler → service function → DB query. Never put SQL in endpoints.
3. **SQL**: Always use asyncpg parameterized queries (`$1, $2, ...`). Never f-strings for user data.
4. **Transactions**: Use `async with conn.transaction()` for any multi-step mutation. Use `SELECT ... FOR UPDATE` when reading a row before modifying it.
5. **Money**: Always use `Decimal` with `ROUND_HALF_UP`. Never `float` for financial values.
6. **Auth**: Protected endpoints use `Depends(require_auth)`. Admin-only use `Depends(require_admin)`.
7. **Rate limiting**: All POST/PATCH/DELETE endpoints must call `check_rate_limit(ip, action=..., limit=..., window_seconds=...)`.
8. **Errors**: Raise `ValueError` for 400, `PermissionError` for 403. Endpoints catch these and convert to `HTTPException`.
9. **XP changes**: After any XP grant, always call `check_level_up()` to trigger grade/level progression.
10. **Notifications**: Emit via `notification_service.create_notification(conn, ...)` inside the parent transaction.

### Frontend
1. **API calls**: Always use `fetchApi<T>()` from `lib/api.ts`. Never call `fetch()` directly.
2. **Auth token**: Never store the access token in localStorage. It lives in a JS module variable.
3. **Error handling**: Catch `ApiError` (not `Response`). Use `(err as ApiError).detail` for messages.
4. **Types**: All API interfaces are defined in `src/lib/api.ts` and `src/types/index.ts`. Keep them in sync with backend Pydantic models.
5. **Loading states**: Every async operation needs `loading`, `error`, and empty-state handling.
6. **Notifications**: Use `useNotifications()` hook. Never fetch notifications directly from a component.

## Naming Conventions
| Context | Convention | Example |
|---------|-----------|---------|
| Python files/functions | snake_case | `quest_service.py`, `create_review()` |
| Python classes | PascalCase | `QuestCreate`, `UserProfile` |
| TS files | kebab-case for pages, PascalCase for components | `page.tsx`, `ReviewList.tsx` |
| TS functions | camelCase | `getUserReviews()`, `fetchApi()` |
| DB columns | snake_case | `stats_int`, `is_read`, `xp_to_next` |
| API paths | kebab-case | `/api/v1/quest-templates`, `/api/v1/read-all` |

## Key Patterns

### Adding a New Backend Endpoint
```python
# 1. Create service function in services/<name>_service.py
async def my_action(conn: asyncpg.Connection, user_id: str, ...) -> dict:
    async with conn.transaction():           # if mutating
        row = await conn.fetchrow(...)
    return {...}

# 2. Add route in endpoints/<name>.py
@router.post("/action", response_model=MyResponse)
async def do_action(
    body: MyRequest,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = request.client.host if request.client else "unknown"
    check_rate_limit(ip, action="my_action", limit=10, window_seconds=60)
    try:
        result = await my_service.my_action(conn, current_user.id, body.field)
        return MyResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# 3. Register in api/v1/api.py
from app.api.v1.endpoints import ..., my_module
api_router.include_router(my_module.router)
```

### Adding a New Frontend API Function
```typescript
// In src/lib/api.ts
export interface MyResponse {
  id: string;
  field: string;
}

export async function myAction(payload: MyPayload): Promise<MyResponse> {
  return fetchApi<MyResponse>(
    "/my-endpoint/",
    { method: "POST", body: JSON.stringify(payload) },
    true,  // requiresAuth
  );
}
```

## Testing
- Backend: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --tb=short`
- Frontend TypeScript: `cd frontend && npx tsc --noEmit`
- Frontend build: `cd frontend && npm run build`

## Known Architecture Facts
- `GET /wallet/balance` does NOT return `total_earned` — compute from transactions if needed
- `GET /api/v1/classes/` returns only **1 class** (berserk) — other 5 classes are not yet implemented
- `reviews.router` must be registered in `api.py` (historical omission — verify on each bootstrap)
- `AdminBroadcastNotificationRequest.user_ids` requires `min_length=1` — empty array triggers 422
- DB sorting for users is `ORDER BY created_at DESC`, not by XP — client-side sort is approximate
