# QuestionWork — Developer Quickstart

This repository contains a full-stack monorepo: FastAPI backend and Next.js frontend.

Environment contract
--------------------

The backend now treats infrastructure URLs differently by environment.

| APP_ENV | DATABASE_URL | REDIS_URL | Notes |
| --- | --- | --- | --- |
| `development` / `dev` | optional local default allowed | optional local default allowed | Intended for local workstations only |
| `staging` | required explicit value | required explicit value | Startup fails if localhost defaults are used |
| `production` / `prod` | required explicit value | required explicit value | Startup also requires `COOKIE_SECURE=True` and non-empty `ADMIN_IP_ALLOWLIST` |

Minimal backend env examples:

Development:

```env
APP_ENV=development
SECRET_KEY=replace-with-local-dev-secret
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/questionwork
REDIS_URL=redis://localhost:6379
FRONTEND_URL=http://localhost:3000
```

Staging / production:

```env
APP_ENV=staging
SECRET_KEY=replace-with-real-secret
DATABASE_URL=postgresql://user:password@db-host:5432/questionwork
REDIS_URL=redis://redis-host:6379/0
FRONTEND_URL=https://your-frontend.example.com
```

Deployment note: withdrawal auto-approve cutover
-----------------------------------------------

When `WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true`, withdrawal auto-approval ownership moves to the trust-layer `worker` + `scheduler` runtime.

Forbidden process in this mode:
- `backend/scripts/process_withdrawals.py`

Required rollout rule:
- disable any cron, Task Scheduler, container command, or process manager entry that still runs `process_withdrawals.py` before enabling `WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED`
- only then start or restart the trust-layer worker and scheduler processes

If the legacy script is started by mistake while the flag is enabled, it now fails immediately with a guard error instead of running alongside the new job path.

Detailed ops docs:
- `docs/ops-withdrawal-cutover-runbook.md`
- `docs/withdrawal-cutover-deploy-checklist.md`

Quickstart (local development):

1. Backend

```powershell
cd backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create a .env from the example and fill values
copy ..\.env.example .env
# start the app
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

3. Database

This project uses Postgres and Alembic for migrations. By default the app expects a Postgres instance at the `DATABASE_URL` you set in `.env`. Use `docker-compose.db.yml` to spin up a local DB during development.

4. Tests & CI

Tests are run with `pytest` (backend) and `npm test` (frontend). CI is planned to run lint, tests and build steps.

More details in `CLAUDE.md`.

Copilot customizations
----------------------

This repository ships native Copilot instructions, skills, agents, prompts, hooks, and a validated workspace MCP config.

Quick reference:
- `docs/copilot-customizations.md`

Development with Docker
-----------------------

Use the provided Docker Compose file to run Postgres and Redis for local development.

1. Start services:

```powershell
# Запускает Postgres и Redis в фоне
docker compose -f docker-compose.dev.yml up -d
```

2. Run backend setup script (will create venv, install deps and apply migrations):

```powershell
cd backend
.\scripts\setup.ps1
```

3. Verify services and open the app:

```powershell
# Показывает состояние контейнеров
docker compose -f docker-compose.dev.yml ps
# Backend: http://localhost:8001/docs
# Frontend: http://localhost:3000
```

Notes:
- The `docker-compose.dev.yml` defines `questionwork_postgres` and `questionwork_redis` services and persistent volumes.
- Ensure Docker Desktop is running before starting services.

Error reporting & tracing
------------------------

You can enable Sentry error reporting by setting `SENTRY_DSN` and an optional `SENTRY_TRACES_SAMPLE_RATE` in your `.env` file. Example:

```
SENTRY_DSN=https://<key>@o0.ingest.sentry.io/0
SENTRY_TRACES_SAMPLE_RATE=0.1
```

When configured the backend will initialize Sentry on startup.

OpenTelemetry (distributed tracing)
----------------------------------

To enable OpenTelemetry tracing and send traces to an OTLP collector, set the following environment variables in your `.env`:

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OTEL_SERVICE_NAME=questionwork-backend
OTEL_SAMPLE_RATE=0.1
```

When `OTEL_EXPORTER_OTLP_ENDPOINT` is provided the backend will initialize an OTLP exporter and instrument FastAPI and Redis for automatic request and Redis command traces. Ensure an OTLP-compatible collector (e.g., OpenTelemetry Collector) is available to receive traces.

Quick local setup with OpenTelemetry Collector
---------------------------------------------

You can run a local OpenTelemetry Collector that simply logs received traces (handy for local verification).

1. Start services (includes collector):

```powershell
docker compose -f docker-compose.dev.yml up -d
```

2. Ensure `OTEL_EXPORTER_OTLP_ENDPOINT` points to the collector (default for local compose):

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

3. Start the backend (see Quickstart) and make a few requests. Then inspect collector logs to see spans printed:

```powershell
docker logs -f questionwork_otel_collector
```

### View in Jaeger UI

The Jaeger all-in-one UI is exposed at:

```
http://localhost:16686
```

Open the UI and search traces by service name `questionwork-backend` (or the value you set in `OTEL_SERVICE_NAME`).

You should see trace records logged by the collector. For production you'll typically configure the collector to export to a tracing backend (Jaeger, Tempo, Honeycomb, etc.).

