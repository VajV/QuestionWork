# Local Infrastructure Recovery And E2E Audit Implementation Plan

> **Status: COMPLETED** — All 5 tasks executed successfully on 2026-03-11.

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore local Postgres-backed backend startup, bring the QuestionWork API back online, and rerun full browser-based role verification for admin, client, and freelancer flows.

**Architecture:** Treat this as an infrastructure-first recovery, not an application-code bugfix. First restore one working Postgres runtime path, then validate schema readiness and backend startup, then rerun Playwright against the live API, and only then investigate any residual frontend runtime issues such as the `/profile` reload error.

**Tech Stack:** Windows services, Docker Desktop, Docker Compose, PostgreSQL 15/17, Alembic, FastAPI, asyncpg, Next.js 14, Playwright browser tools.

---

## File Map

**Primary runtime/config files**
- Modify only if environment facts differ: `backend/.env`
- Read for backend startup path: `backend/scripts/run.ps1`
- Read for setup and migration path: `backend/scripts/setup.ps1`
- Read for backend startup failure point: `backend/app/main.py`
- Read for DB pool and schema checks: `backend/app/db/session.py`
- Read for config defaults and validation: `backend/app/core/config.py`
- Read for local containers: `docker-compose.dev.yml`

**Verification targets**
- Backend health/docs: `http://localhost:8000/docs`
- Frontend app: `http://localhost:3000`
- Backend API probe: `http://localhost:8000/api/v1/meta/world`

**Plan artifact**
- Create: `docs/superpowers/plans/2026-03-11-local-infra-recovery-and-e2e-audit.md`

## Chunk 1: Restore Infrastructure

### Task 1: Choose And Restore A Working Postgres Runtime

**Files:**
- Read: `docker-compose.dev.yml`
- Read: `backend/.env`
- Read: `backend/app/core/config.py`

- [ ] **Step 1: Confirm the current blocker before changing anything**

Run:
```powershell
docker version
Test-NetConnection -ComputerName localhost -Port 5432 | Format-List ComputerName,RemotePort,TcpTestSucceeded
Get-Service *docker* -ErrorAction SilentlyContinue | Select-Object Name,DisplayName,Status
Get-Service | Where-Object { $_.Name -match 'postgres|redis' -or $_.DisplayName -match 'PostgreSQL|Redis' } | Select-Object Name,DisplayName,Status
```

Expected:
- `docker version` has no `Server:` section or errors on `dockerDesktopLinuxEngine`
- `TcpTestSucceeded : False`
- `com.docker.service` is `Stopped`
- at least one local PostgreSQL service is installed but `Stopped`

- [ ] **Step 2: Prefer the Docker path if Docker Desktop can be opened with sufficient rights**

Run manually from Windows:
```powershell
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

Then verify:
```powershell
docker version
```

Expected:
- output includes both `Client:` and `Server:` sections

- [ ] **Step 3: If Docker is available, start database infrastructure only**

Run:
```powershell
cd C:\QuestionWork
docker compose -f docker-compose.dev.yml up -d questionwork_postgres questionwork_redis
docker compose -f docker-compose.dev.yml ps
```

Expected:
- `questionwork_postgres` is `running` or `healthy`
- `questionwork_redis` is `running` or `healthy`

- [ ] **Step 4: If Docker is still unavailable, use the local PostgreSQL fallback instead**

Run manually from an elevated PowerShell or `services.msc`:
```powershell
Start-Service postgresql-x64-15
```

Fallback if 15 is not the intended instance:
```powershell
Start-Service postgresql-x64-17
```

Then verify:
```powershell
Test-NetConnection -ComputerName localhost -Port 5432 | Format-List ComputerName,RemotePort,TcpTestSucceeded
Get-Service postgresql-x64-15, postgresql-x64-17 -ErrorAction SilentlyContinue | Select-Object Name,Status
```

Expected:
- one PostgreSQL service is `Running`
- `TcpTestSucceeded : True`

- [ ] **Step 5: Verify the target database exists and matches `backend/.env`**

Read:
```powershell
Get-Content C:\QuestionWork\backend\.env
```

Inspect DBs:
```powershell
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -h localhost -p 5432 -l
```

If `questionwork` is missing, create it:
```powershell
& "C:\Program Files\PostgreSQL\15\bin\createdb.exe" -U postgres -h localhost -p 5432 questionwork
```

Expected:
- `DATABASE_URL` in `backend/.env` points to the running instance
- database `questionwork` exists

- [ ] **Step 6: Update `backend/.env` only if the actual local credentials differ**

Modify if needed:
- `backend/.env`

Rules:
- keep `APP_ENV=development`
- change only `DATABASE_URL` or `REDIS_URL` when the live local services use different credentials or ports
- do not change app code for this step

Expected:
- `backend/.env` matches the real local service endpoints

### Task 2: Bring Schema To Current Head

**Files:**
- Read: `backend/alembic.ini`
- Read: `backend/scripts/setup.ps1`
- Read: `backend/app/db/session.py`

- [ ] **Step 1: Activate the backend environment**

Run:
```powershell
cd C:\QuestionWork\backend
.\.venv\Scripts\Activate.ps1
```

Expected:
- venv activates without errors

- [ ] **Step 2: Run Alembic migrations to the current head**

Run:
```powershell
alembic -c alembic.ini upgrade head
```

Expected:
- Alembic finishes without revision conflicts
- no duplicate revision or missing dependency errors

- [ ] **Step 3: Verify required schema objects that backend startup checks depend on**

Run:
```powershell
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -h localhost -p 5432 -d questionwork -c "\dt public.quests"
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -h localhost -p 5432 -d questionwork -c "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='quests' AND column_name='platform_fee_percent';"
```

Expected:
- table `public.quests` exists
- column `platform_fee_percent` exists

- [ ] **Step 4: Stop and investigate only if schema verification fails**

If migration or schema checks fail:
- inspect `backend/alembic/versions/`
- inspect current DB revision with:
```powershell
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -h localhost -p 5432 -d questionwork -c "SELECT * FROM alembic_version;"
```
- compare against prior repo note in `/memories/repo/questionwork-alembic-duplicate-revision-recovery.md`

Expected:
- either schema is correct, or the next blocker is narrowed to a migration issue instead of generic startup failure

## Chunk 2: Re-Enable API And Re-Verify Product Flows

### Task 3: Start Backend And Validate API Availability

**Files:**
- Read: `backend/scripts/run.ps1`
- Read: `backend/app/main.py`

- [ ] **Step 1: Start the backend using the repository’s canonical script**

Run:
```powershell
cd C:\QuestionWork\backend
.\scripts\run.ps1
```

Expected:
- Uvicorn starts successfully
- no `OSError` from `asyncpg.create_pool`
- no startup exit during lifespan

- [ ] **Step 2: Verify API reachability from outside the process**

Run in another terminal:
```powershell
Invoke-WebRequest http://127.0.0.1:8000/docs | Select-Object StatusCode
Invoke-WebRequest http://127.0.0.1:8000/api/v1/meta/world | Select-Object StatusCode
```

Expected:
- `/docs` returns `200`
- `/api/v1/meta/world` returns `200` or a valid API-level status, but not connection refusal

- [ ] **Step 3: Verify Redis only if a feature now fails specifically on Redis access**

If Redis was started via Docker:
```powershell
docker compose -f C:\QuestionWork\docker-compose.dev.yml ps questionwork_redis
```

If using a local Redis install, verify its configured port separately.

Expected:
- no Redis-specific runtime errors in backend logs during auth refresh or rate-limited endpoints

### Task 4: Re-Run Browser Verification For Real Roles

**Files:**
- Read: `frontend/src/context/AuthContext.tsx`
- Read: `frontend/src/lib/api.ts`
- Read: `frontend/src/app/admin/layout.tsx`

- [ ] **Step 1: Restart frontend if its dev server is stale**

Run:
```powershell
cd C:\QuestionWork\frontend
npm run dev
```

Expected:
- `/` and static assets load without 404s on `/_next/...`

- [ ] **Step 2: Verify anonymous public pages now fetch real data**

Check in browser:
- `/`
- `/quests`
- `/marketplace`

Expected:
- console no longer shows `ERR_CONNECTION_REFUSED` to backend
- `/quests` loads actual quest data or a valid empty-state from API
- `/marketplace` loads real talent market data or a valid empty-state from API

- [ ] **Step 3: Verify auth flows end-to-end**

Scenarios:
- login with an existing test user
- register a new freelancer
- register a new client
- refresh session on reload
- logout

Expected:
- login no longer ends in `Failed to fetch`
- registration returns a session and routes into authenticated UI
- page reload preserves valid auth state through refresh flow

- [ ] **Step 4: Verify client flow end-to-end**

Scenarios:
- login as client
- open `/quests/create`
- create a quest
- inspect quest in `/quests`
- verify redirect and protected access behavior from authenticated state

Expected:
- quest creation succeeds
- created quest is visible in market or client profile views

- [ ] **Step 5: Verify freelancer flow end-to-end**

Scenarios:
- login as freelancer
- browse `/quests`
- apply filters
- open a quest detail page
- submit an application if the environment has a suitable quest

Expected:
- freelancer can browse and interact with real quest data
- no auth or API connectivity failures remain

- [ ] **Step 6: Verify admin flow end-to-end**

Scenarios:
- login as admin
- open `/admin`
- complete TOTP gate if required
- visit `/admin/users`, `/admin/quests`, `/admin/logs`, `/admin/withdrawals`

Expected:
- admin layout no longer blocks on backend reachability
- TOTP behavior reflects actual backend policy instead of connection failure

### Task 5: Investigate Residual Frontend Runtime Errors Only After API Recovery

**Files:**
- Read: `frontend/src/app/profile/page.tsx`
- Read: `frontend/src/app/profile/dashboard/page.tsx`
- Read: `frontend/src/context/AuthContext.tsx`

- [ ] **Step 1: Reproduce the `/profile` full-reload warning after backend recovery**

Run/observe:
- open `/profile`
- watch the frontend terminal
- capture the exact stack trace if `Fast Refresh had to perform a full reload due to a runtime error` appears again

Expected:
- either no runtime error remains, or there is now a reproducible frontend-only stack trace

- [ ] **Step 2: If the error remains, isolate it before editing code**

Collect:
- browser console stack trace
- frontend terminal stack trace
- exact route and auth state
- failing network request, if any

Expected:
- the `/profile` issue is reduced to a concrete code defect rather than mixed with infra failures

- [ ] **Step 3: Create a separate remediation plan if `/profile` still fails**

Do not mix this with infrastructure recovery. Create a new plan dedicated to the profile runtime bug.

Expected:
- infra recovery stays narrowly scoped and verifiable

## Verification Checklist

- [x] `docker version` shows a reachable server, or a local PostgreSQL service is running on `5432`
- [x] `Test-NetConnection localhost -Port 5432` succeeds
- [x] `alembic -c alembic.ini upgrade head` succeeds
- [x] `backend/scripts/run.ps1` starts Uvicorn without DB startup errors
- [x] `http://localhost:8000/docs` is reachable
- [x] `http://localhost:8000/api/v1/meta/world` is reachable
- [x] frontend pages no longer show `ERR_CONNECTION_REFUSED`
- [x] login and registration stop failing with `Failed to fetch`
- [x] admin, client, and freelancer flows can be audited against a live backend

## Execution Results (2026-03-11)

### Infrastructure
- Docker Desktop started successfully (v29.1.3 / Desktop v4.57.0)
- `questionwork_postgres` and `questionwork_redis` containers healthy
- Alembic schema already at head — no pending migrations
- Backend running on `localhost:8000`, frontend on `localhost:3001` (3000 occupied)

### E2E Browser Verification
- **Landing page**: Live data — 148 contracts, $1.2k avg reward, leaderboard, activity feed
- **Quests page**: 10 open quests, filters work, quest cards render correctly
- **Marketplace**: Renders with tabs, grade filters, search, sort
- **Login/logout**: `novice_dev` / `password123` works, redirects to `/profile`
- **Registration**: Created `test_e2e_freelancer` (freelancer) and `test_e2e_client` (client)
- **Client quest creation**: Created "E2E Test Quest - Build API Module" (5000₽, Junior, Python)
- **Freelancer application**: `novice_dev` successfully applied to the new quest with cover letter
- **Admin dashboard**: 90 users, 46 quests, 6200₽ revenue, all admin pages functional
- **Admin users/quests/logs/withdrawals**: All render with data, filters, pagination

### Issues Found & Fixed
1. **`/admin` redirect hooks crash** — Server Component `redirect()` caused "Rendered more hooks than during the previous render" during client-side navigation. Fixed by converting to client component with `useRouter().replace()`.
2. **`/profile` runtime error** — Not reproducible with live backend. Was caused by backend being offline.
3. **`questionwork_otel_collector` container** keeps restarting — non-blocking, doesn't affect functionality.

## Notes

- Do not edit application code until one database path is proven working.
- Do not chase frontend `Failed to fetch` symptoms while backend is offline.
- If starting services requires elevation, perform only the minimal privileged steps needed to get Postgres running.
- If both Docker and local PostgreSQL remain blocked by permissions, the next action is not a code fix; it is to obtain a session with sufficient Windows service-control rights.
