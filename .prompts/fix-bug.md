# Prompt: Fix a Bug

Use this structured workflow to diagnose and fix bugs in QuestionWork.

---

## Step 1 — Reproduce and characterise

Determine:
- **Symptom**: what the user sees (error message / wrong value / 404 / etc.)
- **Layer**: frontend-only / API communication / backend logic / database
- **HTTP status**: if available — 404, 422, 500, etc.

Quick classification by symptom:

| Symptom | Likely layer | First place to check |
|---------|-------------|----------------------|
| "Not found" / 404 on any endpoint | Router registration | `backend/app/api/v1/api.py` |
| 422 Unprocessable Entity | Request validation | Pydantic model field constraints |
| 500 Internal Server Error | Backend logic / DB | uvicorn logs, service function |
| `NaN` or `undefined` in UI | Missing field in API response | Backend response model vs frontend interface |
| Auth error / 401 | JWT or dependency | `core/security.py`, `require_auth` dep |
| Error message says "Ошибка…" without detail | Frontend error handling | `instanceof Response` / `ApiError` pattern |
| Wrong data shown (stale / wrong sort) | Caching or wrong query | Service SQL, frontend state management |

---

## Step 2 — Backend investigation checklist

Run through these in order — stop at the first match:

### 2a. Router registered?
```bash
cd backend && .venv/Scripts/python.exe -c \
  "from app.main import app; [print(r.path, r.methods) for r in app.routes]"
```
- If the path is missing → add import + `include_router()` to `api/v1/api.py`

### 2b. Correct HTTP method and path?
- Check the frontend call in `frontend/src/lib/api.ts` — method, path, trailing slash
- Compare to `@router.<method>("/<path>")` in the endpoint file

### 2c. Request model validation?
- If 422: read the Pydantic model for the endpoint
- Common traps: `min_length=1` on list fields, missing required fields, wrong types
- Fix: relax constraint OR fix the frontend payload

### 2d. Service/business logic?
- Read the relevant function in `backend/app/services/`
- Check for: missing `await`, wrong SQL column name, missing `str()` cast on UUID, bare `float` instead of `Decimal`

### 2e. Response model missing a field?
- Compare the `dict(row)` returned by the service to the `*Response` Pydantic model
- If a field is in the DB row but not in the response model → add it
- If a field is computed (e.g. `total_earned`) → add the SELECT clause or compute it

### 2f. Transaction / race condition?
- If data is sometimes missing: ensure `async with conn.transaction()` wraps the mutation
- If a row was modified between read and write: add `SELECT ... FOR UPDATE`

---

## Step 3 — Frontend investigation checklist

### 3a. API function correct?
- Open `frontend/src/lib/api.ts`, find the function calling the affected endpoint
- Check: method, path spelling, auth flag (`true` = Bearer token required)
- Check: is the response interface missing a field that the backend now returns?

### 3b. Error handling?
```typescript
// WRONG — fetchApi throws ApiError, not Response:
catch (err) { if (err instanceof Response) ... }

// CORRECT:
catch (err) { const msg = (err as ApiError).detail ?? "Unknown error"; }
```

### 3c. State not updating?
- Is the component re-fetching after mutation? (look for `fetchData()` call after await)
- Is the stale state being read from a closed-over variable? (use functional setState)

### 3d. `NaN` / `undefined` in render?
- Add a guard: `value ?? 0` or `value || "—"`
- Trace back: which API field is missing? → fix root cause in backend response model
- Do NOT paper over with `|| 0` permanently — fix the backend field

### 3e. TypeScript error?
```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -A3 "error TS"
```

---

## Step 4 — Write and apply the fix

1. Make the minimal change needed
2. If it touches SQL → ensure parameterized query ($1, $2, …)
3. If it adds a new field to a response model → check if Alembic migration is needed
4. If it changes a Pydantic model → update the matching TS interface in `api.ts` / `types/index.ts`
5. If XP is now granted → add `check_level_up()` call
6. If a mutation is added → add `check_rate_limit()` call

---

## Step 5 — Verify the fix

```bash
# Backend tests
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --tb=short

# TypeScript check
cd frontend && npx tsc --noEmit

# Targeted smoke test (replace path/payload)
curl -s http://localhost:8001/api/v1/<affected-path> \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

---

## Known recurring bugs in this codebase

| Bug pattern | Root cause | Fix |
|-------------|-----------|-----|
| Any endpoint returns 404 | Router not in `api.py` | Add import + `include_router()` |
| Broadcast notification sends 0 | `user_ids=[]` hits `min_length=1` | Validate non-empty OR change backend to allow empty = "all users" |
| NaN in wallet "total earned" | `/wallet/balance` missing `total_earned` field | Add field to SQL SELECT + response model |
| Class selector shows only 1 class | `CLASS_REGISTRY` stub has only berserk | Implement remaining 5 classes in `core/classes.py` |
| Error detail never shown in ClassSelector | `instanceof Response` instead of `ApiError` | Fix catch block to use `(err as ApiError).detail` |
| Reviews 404 | `reviews.router` not registered | Add to `api/v1/api.py` |
