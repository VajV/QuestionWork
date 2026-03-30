# Trust-Layer Step 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Step 1 infrastructure for the PostgreSQL + ARQ + Redis trust layer: schema migrations, repository layer, ARQ bootstrap, worker service, and scheduler service.

**Architecture:** Keep PostgreSQL as the durable source of truth and introduce a thin execution layer around it rather than moving business logic into Redis or scripts. Step 1 stops at infrastructure: it creates the durable command/job model, queue bootstrap, process skeletons, and recovery plumbing needed before migrating money, email, or admin handlers.

**Tech Stack:** FastAPI, asyncpg, PostgreSQL, Alembic, Redis, ARQ, Prometheus client, OpenTelemetry, PowerShell, pytest

---

## Scope Guardrails
- This plan covers only Step 1 from the approved spec.
- Do not move withdrawal, lifecycle email, or admin force-action business logic into jobs yet.
- Do not change public API behavior yet except where small internal hooks are needed for shared infrastructure.
- End-to-end domain jobs for money/email/admin belong to later plans.
- The centralized rate-limit policy registry is explicitly deferred to the later rate-limit implementation step; Step 1 only preserves compatibility with the current rate-limit system.

## File Structure
- Modify: `backend/requirements.txt` — add ARQ dependency and keep backend runtime dependencies explicit.
- Modify: `backend/app/core/config.py` — add queue/runtime settings for worker and scheduler processes.
- Modify: `backend/app/core/redis_client.py` — expose a safe Redis connection path for ARQ bootstrap while preserving current cached client behavior.
- Modify: `backend/app/db/session.py` — expose reusable pool/bootstrap helpers for non-HTTP processes.
- Modify: `backend/app/db/models.py` — keep ORM parity for new tables and extra audit/email linkage columns.
- Create: `backend/alembic/versions/20260314_01_add_command_job_baseline_tables.py` — add `command_requests`, `background_jobs`, `background_job_attempts`, runtime heartbeat table, and alignment columns on `admin_logs` / `email_outbox`.
- Create: `backend/app/repositories/__init__.py` — repository package entrypoint.
- Create: `backend/app/repositories/command_repository.py` — CRUD and state transitions for `command_requests`.
- Create: `backend/app/repositories/job_repository.py` — durable job creation, claim, heartbeat, retry scheduling, and enqueue bookkeeping.
- Create: `backend/app/repositories/runtime_heartbeat_repository.py` — worker/scheduler liveness writes and reads.
- Create: `backend/app/jobs/__init__.py` — jobs package entrypoint.
- Create: `backend/app/jobs/enums.py` — central constants for job statuses, command statuses, queue names, and runtime kinds.
- Create: `backend/app/jobs/context.py` — shared typed context object for worker/scheduler execution.
- Create: `backend/app/jobs/arq.py` — ARQ Redis settings, queue names, enqueue helper, and worker settings factory.
- Create: `backend/app/jobs/registry.py` — handler registry and internal Step 1 bootstrap jobs.
- Create: `backend/app/jobs/handlers/__init__.py` — handlers package entrypoint.
- Create: `backend/app/jobs/handlers/ops_noop.py` — internal no-op handler used to prove queue → DB → worker flow in Step 1.
- Create: `backend/app/jobs/worker.py` — worker process entrypoint, claim/execute/update loop integration, and startup/shutdown hooks.
- Create: `backend/app/jobs/scheduler.py` — scheduler process entrypoint for orphaned queued jobs, retry-scheduled jobs, and stale-running recovery.
- Create: `backend/scripts/run_worker.ps1` — local worker runner script.
- Create: `backend/scripts/run_scheduler.ps1` — local scheduler runner script.
- Modify: `scripts/start-all.ps1` — optionally launch worker and scheduler after backend migration/startup checks pass.
- Test: `backend/tests/test_command_repository.py` — command persistence and dedupe tests.
- Test: `backend/tests/test_job_repository.py` — job lifecycle, claim, retry, and enqueue bookkeeping tests.
- Test: `backend/tests/test_job_runtime.py` — ARQ bootstrap, noop handler execution, and runtime heartbeat tests.
- Test: `backend/tests/test_scheduler_runtime.py` — orphaned queue recovery and stale-running rescue tests.

---

## Chunk 1: Durable Schema And Repository Layer

### Task 1: Add Step 1 runtime dependencies and settings

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/redis_client.py`

- [ ] **Step 1: Add ARQ to backend dependencies**

Update `backend/requirements.txt` to include a pinned `arq` version compatible with Redis 5 and Python 3.12.

- [ ] **Step 2: Add queue/runtime settings to config**

Add settings for:
- ARQ Redis URL override if different from app Redis
- default queue names
- scheduler poll interval
- worker heartbeat interval
- stale-running timeout
- orphaned-queued recovery interval

Validation rule:
- stale-running timeout must be greater than worker heartbeat interval

- [ ] **Step 3: Reuse Redis bootstrap safely**

Extend `backend/app/core/redis_client.py` so ARQ bootstrap can obtain Redis settings without breaking the current cached `redis-py` client used by rate limiting.

- [ ] **Step 4: Add focused config tests if validation rules change**

If new required settings add validation logic, extend `backend/tests/test_config_validation.py` instead of creating a duplicate test file.

- [ ] **Step 5: Verify backend imports still load**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_config_validation.py -q --tb=short`
Expected: PASS

---

### Task 2: Create the durable schema for commands, jobs, attempts, and runtime heartbeats

**Files:**
- Create: `backend/alembic/versions/20260314_01_add_command_job_baseline_tables.py`
- Modify: `backend/app/db/models.py`

- [ ] **Step 1: Write the migration for new trust-layer tables**

Create the Alembic migration with:
- `command_requests`
- `background_jobs`
- `background_job_attempts`
- `runtime_heartbeats`
- extra columns on `admin_logs`
- extra columns on `email_outbox`
- indexes and constraints from the approved spec

Use these exact Step 1 alignment columns:
- `admin_logs.command_id`, `admin_logs.job_id`, `admin_logs.request_id`, `admin_logs.trace_id`
- `email_outbox.command_id`, `email_outbox.job_id`, `email_outbox.dedupe_key`, `email_outbox.provider_message_id`, `email_outbox.last_attempt_at`, `email_outbox.next_attempt_at`

Use this exact `runtime_heartbeats` table shape:
- `id uuid primary key`
- `runtime_kind text not null`
- `runtime_id text not null`
- `hostname text not null`
- `pid integer not null`
- `started_at timestamptz not null`
- `last_seen_at timestamptz not null`
- `meta_json jsonb not null default '{}'::jsonb`
- unique `(runtime_kind, runtime_id)`
- index on `(runtime_kind, last_seen_at)`

Treat `runtime_heartbeats` as an inferred Step 1 implementation detail derived from the spec's recovery SLA and heartbeat requirements, not as a new domain concept.

- [ ] **Step 2: Keep ORM parity in `models.py`**

Add SQLAlchemy ORM models or column extensions so local tooling and future admin/reporting code can see the same schema shape.

- [ ] **Step 3: Add downgrade logic that only removes Step 1 artifacts**

The downgrade must reverse new tables and newly added columns only, without touching existing `admin_logs` or `email_outbox` base structures.

- [ ] **Step 4: Apply migration on a local database**

Run: `cd backend; .venv/Scripts/python.exe -m alembic upgrade head`
Expected: upgrade succeeds with one new head applied and no duplicate-head regression.

- [ ] **Step 5: Verify Alembic head integrity**

Run: `cd backend; .venv/Scripts/python.exe -m alembic heads`
Expected: exactly one head is shown.

- [ ] **Step 6: Verify migration syntax before broader implementation**

Run: `cd backend; .venv/Scripts/python.exe -m alembic upgrade head --sql > NUL`
Expected: migration renders SQL successfully without statement/DDL errors.

---

### Task 3: Build repositories for commands, jobs, and runtime heartbeats

**Files:**
- Create: `backend/app/repositories/__init__.py`
- Create: `backend/app/repositories/command_repository.py`
- Create: `backend/app/repositories/job_repository.py`
- Create: `backend/app/repositories/runtime_heartbeat_repository.py`
- Modify: `backend/app/db/session.py`
- Test: `backend/tests/test_command_repository.py`
- Test: `backend/tests/test_job_repository.py`

- [ ] **Step 1: Write repository tests before implementation**

Cover at minimum:
- create command with dedupe key
- find existing active command by dedupe key
- return replay-eligible succeeded command within retention window
- create job linked to command
- claim queued job exactly once
- concurrent claim attempt loses cleanly without double-running the job
- schedule retry on retryable failure
- mark terminal failure without retry
- mark dead-letter when retry budget is exhausted
- mark enqueue success and enqueue failure bookkeeping
- write and read runtime heartbeat
- roll back partial repository transaction when later step in the same transaction fails

Reference these spec invariants explicitly in the test names or comments:
- `Explicit State Machine`
- `Dedupe and Idempotency Rules`
- `Recovery SLA`

Example naming pattern:
- `test_command_dedupe_key_replay_within_retention_window_returns_existing_command`
- `test_job_claim_state_machine_allows_only_one_worker_to_transition_queued_to_running`
- `test_stale_running_recovery_clears_lock_fields_and_reuses_same_job_id`

- [ ] **Step 2: Add reusable DB helpers for non-HTTP processes**

Extend `backend/app/db/session.py` with helpers the worker and scheduler can use directly, instead of duplicating pool/bootstrap logic in new runtime modules.

- [ ] **Step 3: Implement `command_repository.py` minimally**

Keep it focused on:
- insert accepted command
- fetch by id
- fetch active/replay-eligible command by dedupe key
- transition command status safely

Freeze this method inventory before writing code:
- `create_command(...)`
- `get_command_by_id(...)`
- `find_replayable_command_by_dedupe_key(...)`
- `mark_command_running(...)`
- `mark_command_succeeded(...)`
- `mark_command_failed(...)`
- `mark_command_cancelled(...)`

- [ ] **Step 4: Implement `job_repository.py` minimally**

Keep it focused on:
- insert queued job
- claim job with atomic status transition
- persist attempt row
- mark running/succeeded/failed/retry-scheduled/dead-letter
- update heartbeat
- fetch orphaned queued jobs and stale running jobs
- record ARQ enqueue success/failure

Use repository methods, not free-form queries, for these scheduler/worker-sensitive transitions:
- clear stale lock and move `running -> retry_scheduled`
- mark command `accepted -> running` when a job is claimed
- mark linked command terminal when a job reaches `failed` or `dead_letter`

Freeze this method inventory before writing code:
- `create_job(...)`
- `get_job_by_id(...)`
- `claim_job(...)`
- `insert_attempt(...)`
- `mark_job_succeeded(...)`
- `mark_job_retry_scheduled(...)`
- `mark_job_failed(...)`
- `mark_job_dead_letter(...)`
- `record_enqueue_success(...)`
- `record_enqueue_failure(...)`
- `find_orphaned_queued_jobs(...)`
- `find_due_retry_jobs(...)`
- `find_stale_running_jobs(...)`
- `rescue_stale_running_job(...)`
- `touch_job_heartbeat(...)`

- [ ] **Step 5: Implement `runtime_heartbeat_repository.py` minimally**

Keep it focused on:
- upsert worker/scheduler heartbeat row
- fetch stale runtime rows for diagnostics/tests

Freeze this method inventory before writing code:
- `upsert_runtime_heartbeat(...)`
- `get_runtime_heartbeat(...)`
- `find_stale_runtimes(...)`

- [ ] **Step 6: Run focused repository tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_command_repository.py tests/test_job_repository.py -q --tb=short`
Expected: PASS

---

## Chunk 2: ARQ Bootstrap And Worker Service

### Task 4: Build the ARQ bootstrap surface and internal job registry

**Files:**
- Create: `backend/app/jobs/__init__.py`
- Create: `backend/app/jobs/enums.py`
- Create: `backend/app/jobs/context.py`
- Create: `backend/app/jobs/arq.py`
- Create: `backend/app/jobs/registry.py`
- Create: `backend/app/jobs/handlers/__init__.py`
- Create: `backend/app/jobs/handlers/ops_noop.py`
- Test: `backend/tests/test_job_runtime.py`

- [ ] **Step 1: Write runtime tests for bootstrap and registry behavior**

Cover at minimum:
- ARQ settings are built from config predictably
- registry returns the noop handler for its kind
- noop handler returns deterministic payload for smoke verification

- [ ] **Step 2: Centralize enums and queue names**

Create a single source of truth for:
- command statuses
- job statuses
- queue names
- runtime kinds

- [ ] **Step 3: Add a shared runtime context object**

The context should carry only cross-cutting runtime concerns needed by handlers and process loops:
- db connection/pool access
- worker id
- trace/request ids when present
- current time / heartbeat metadata helpers

Also define the handler contract here and enforce it in tests:
- `kind`
- `queue_name`
- `max_attempts`
- `backoff_seconds(attempt_no, error_code) -> int`
- `is_retryable(error) -> bool`
- `execute(conn, payload, context) -> dict`
- optional `transaction_isolation` metadata for later money/admin handlers

- [ ] **Step 4: Implement ARQ bootstrap module**

`backend/app/jobs/arq.py` should provide:
- Redis connection settings for ARQ
- enqueue-by-job-id helper
- worker settings factory
- ARQ payload validation for `{job_id, trace_id?, request_id?}` only
- no direct domain logic

- [ ] **Step 5: Register one internal Step 1 handler**

Add `ops.noop` as the only executable Step 1 job so the new infrastructure can be verified without migrating money/email/admin behavior yet.

- [ ] **Step 6: Run focused runtime bootstrap tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_job_runtime.py -q --tb=short -k "registry or noop or arq"`
Expected: PASS

---

### Task 5: Implement the worker process skeleton

**Files:**
- Create: `backend/app/jobs/worker.py`
- Modify: `backend/app/jobs/arq.py` — expose worker initialization helpers and message decoding contract
- Modify: `backend/app/jobs/registry.py` — expose lookup by job kind for the worker execution loop
- Test: `backend/tests/test_job_runtime.py`

- [ ] **Step 1: Write failing worker lifecycle tests**

Cover at minimum:
- worker claims a queued job once
- worker writes a fresh `lock_token` and `locked_by` value on claim
- worker inserts an attempt row
- worker marks command running when job is claimed
- worker completes noop job as succeeded
- worker records retry scheduling on injected retryable failure
- worker marks terminal failure without retry on injected non-retryable failure
- worker marks dead-letter when max attempts is exceeded

- [ ] **Step 2: Implement startup and shutdown hooks**

The worker process must:
- initialize DB access
- initialize Redis/ARQ access
- install consistent logging/tracing hooks
- close resources cleanly on shutdown

Define runtime identity here:
- `worker_id = "{hostname}:{pid}"`
- `lock_token = uuid4()` on each successful claim

- [ ] **Step 3: Implement the claim → execute → persist loop**

Use repositories for all state transitions. Do not inline raw SQL in the worker entrypoint.

The loop must explicitly:
- decode and validate the ARQ message payload shape
- fetch the durable job by `job_id`
- resolve handler by `job.kind`
- propagate `trace_id` and `request_id` into runtime context before execution
- call `handler.is_retryable(...)` to classify exceptions
- call `handler.backoff_seconds(...)` to compute `available_at` for retry scheduling

- [ ] **Step 4: Add heartbeat updates for long-running execution**

Even though `ops.noop` is fast, wire the heartbeat mechanism now so real handlers can reuse it later.

Implementation expectation:
- heartbeat interval comes from config
- the worker loop owns heartbeat writes, not individual handlers
- long-running means any execution lasting longer than one heartbeat interval

- [ ] **Step 5: Run focused worker tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_job_runtime.py -q --tb=short -k "worker"`
Expected: PASS

---

## Chunk 3: Scheduler Service And Local Runtime Integration

### Task 6: Implement the scheduler process skeleton

**Files:**
- Create: `backend/app/jobs/scheduler.py`
- Modify: `backend/app/repositories/job_repository.py`
- Modify: `backend/app/repositories/runtime_heartbeat_repository.py`
- Test: `backend/tests/test_scheduler_runtime.py`

- [ ] **Step 1: Write failing scheduler tests**

Cover at minimum:
- scheduler finds queued jobs with missing `enqueued_at` and re-enqueues them
- scheduler finds `retry_scheduled` jobs whose `available_at <= now()` and re-enqueues them
- scheduler rescues stale `running` jobs by clearing lock fields and returning them to `retry_scheduled`
- scheduler rescue reuses the same `job_id` and never creates a duplicate command or job row
- scheduler writes its own runtime heartbeat

- [ ] **Step 2: Implement one scheduler tick function**

Keep the first implementation as a testable pure orchestration unit that performs one pass over:
- orphaned queued jobs
- due retry-scheduled jobs
- stale running jobs

Use a function shape close to:
- `async def scheduler_tick(...) -> dict[str, int]`

The tick must use configuration-backed intervals from `config.py`, including:
- scheduler poll interval
- stale-running timeout
- orphaned-queued recovery interval

Use repository-mediated mutations only. Scheduler recovery transactions should remain at normal application isolation unless later testing proves a stronger level is required.

Make the data-access sequence explicit:
- `find_orphaned_queued_jobs()`
- `find_due_retry_jobs()`
- `find_stale_running_jobs()`
- `rescue_stale_running_job()`
- shared ARQ enqueue helper for each recovered/enqueued job

- [ ] **Step 3: Wrap the tick function in a long-running scheduler service**

Add polling, structured logs, graceful shutdown, and runtime heartbeat updates.

The long-running loop must call ARQ re-enqueue through the shared enqueue helper in `backend/app/jobs/arq.py`, not through ad hoc Redis pushes or repository-side queue logic.

- [ ] **Step 4: Keep scheduler free of domain-specific scan logic**

Do not add withdrawal/email/admin business scans in Step 1. Limit the scheduler to queue-health and infrastructure recovery behavior.

- [ ] **Step 5: Run focused scheduler tests**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_scheduler_runtime.py -q --tb=short`
Expected: PASS

---

### Task 7: Add local runner scripts and start-up integration

**Files:**
- Create: `backend/scripts/run_worker.ps1`
- Create: `backend/scripts/run_scheduler.ps1`
- Modify: `scripts/start-all.ps1`

- [ ] **Step 1: Add a worker runner script**

Create a PowerShell entrypoint that:
- activates the backend venv
- checks required env/config
- starts the worker process using the new module entrypoint

- [ ] **Step 2: Add a scheduler runner script**

Create a PowerShell entrypoint with the same bootstrap behavior for the scheduler process.

- [ ] **Step 3: Wire local orchestration conservatively**

Update `scripts/start-all.ps1` to launch worker and scheduler only after DB startup, migrations, and backend health checks succeed. Keep failure output readable and isolated per process.

- [ ] **Step 4: Smoke-test local runners**

Run:
- `cd backend; powershell -File scripts/run_worker.ps1`
- `cd backend; powershell -File scripts/run_scheduler.ps1`

Expected: both processes start without import/config errors and emit startup logs.

- [ ] **Step 5: Verify startup fails cleanly on missing critical config**

Temporarily unset one required runtime variable in a disposable shell and rerun one of the scripts.
Expected: process exits early with a clear config error instead of hanging or crashing later.

---

### Task 8: Run the Step 1 verification slice

**Files:**
- Test: `backend/tests/test_command_repository.py`
- Test: `backend/tests/test_job_repository.py`
- Test: `backend/tests/test_job_runtime.py`
- Test: `backend/tests/test_scheduler_runtime.py`

- [ ] **Step 1: Run the full Step 1 targeted test slice**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_command_repository.py tests/test_job_repository.py tests/test_job_runtime.py tests/test_scheduler_runtime.py -q --tb=short`
Expected: PASS

- [ ] **Step 2: Run a protection slice against existing platform plumbing**

Run: `cd backend; .venv/Scripts/python.exe -m pytest tests/test_config_validation.py tests/test_ratelimit.py tests/test_lifecycle.py tests/test_withdrawal.py -q --tb=short`
Expected: PASS

- [ ] **Step 3: Verify migrations are clean on a fresh database state**

Run:
- `cd backend; .venv/Scripts/python.exe -m alembic downgrade -1`
- `cd backend; .venv/Scripts/python.exe -m alembic upgrade head`

Expected: downgrade and re-upgrade succeed without schema drift in the new Step 1 tables.

Precondition:
- run this on a disposable local database or a reset dev database, not against shared data with active application traffic.

- [ ] **Step 4: Verify downgrade actually removes Step 1 schema artifacts**

After `alembic downgrade -1`, confirm the new Step 1 tables are absent before re-upgrading.
Expected: `command_requests`, `background_jobs`, `background_job_attempts`, and `runtime_heartbeats` are no longer present.

- [ ] **Step 5: Verify the noop end-to-end flow manually**

With API-independent test bootstrap or a small test harness, create one `command_requests` row + one `background_jobs` row for `ops.noop`, enqueue it through ARQ, and confirm:
- command transitions `accepted -> running -> succeeded`
- job transitions `queued -> running -> succeeded`
- one attempt row is written
- `enqueued_at` and runtime heartbeat rows are populated

---

## Implementation Notes
- Keep repository files small and responsibility-specific. Do not build a generic ORM abstraction layer.
- Keep ARQ messages minimal: `job_id`, `trace_id`, `request_id` only.
- If repository tests become awkward because of repeated row setup, add tiny test helpers in the test files before adding shared fixtures to `conftest.py`.
- Do not wire public admin/API status endpoints in Step 1 unless a missing internal hook makes repository or runtime verification impossible.

## Exit Criteria For Step 1
- New Step 1 tables and alignment columns exist and migrate cleanly.
- Repositories cover command/job creation, claim, retry, enqueue bookkeeping, and heartbeat writes.
- ARQ bootstrap is live and can execute `ops.noop` end-to-end.
- Worker and scheduler run as separate local processes.
- Scheduler can recover orphaned queued jobs and stale running jobs.
- Existing rate limit, lifecycle, and withdrawal tests still pass after infrastructure changes.
- Step 1 registers only internal infrastructure handlers like `ops.noop`; money/email/admin domain handlers remain intentionally unregistered.

Plan complete and saved to `docs/superpowers/plans/2026-03-14-trust-layer-step1-implementation-plan.md`. Ready to execute?