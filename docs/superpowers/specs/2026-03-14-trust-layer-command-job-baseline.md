# QuestionWork Trust-Layer Command/Job Baseline

Date: 2026-03-14
Status: proposed baseline, approved for planning
Scope: money flows, email delivery, admin actions, production rate limiting, observability

## Goal
Build a single operational layer where PostgreSQL is the source of truth for command state, job lifecycle, retries, deduplication, errors, and audit history, while Redis is used only for transport and coordination via ARQ.

This layer must unify:
- high-risk money operations
- email dispatch and lifecycle messaging
- async admin actions
- production rate-limit policy management
- observability across API, worker, and scheduler

## Why This Architecture
- Existing code already contains partial building blocks: Redis-backed rate limiting, persistent email outbox, withdrawal processor scripts, and OTEL/Prometheus setup.
- The current problem is operational fragmentation, not a total absence of mechanisms.
- A PostgreSQL + ARQ + Redis command/job layer gives stronger reliability than cron scripts alone without introducing workflow-engine complexity too early.

## Non-Goals
- Not a full workflow orchestration platform.
- Not event sourcing for all domain entities.
- Not replacing existing domain tables like transactions, notifications, or quests.
- Not making every admin action asynchronous. Only high-risk, heavy, or externally-coupled actions move into the command/job layer.

## Core Principles
- PostgreSQL is the source of truth for state, status transitions, attempts, errors, and audit history.
- Redis is ephemeral transport and coordination only. Losing Redis must not lose business truth.
- API accepts commands, persists them transactionally, then enqueues jobs.
- Workers execute idempotent handlers and persist all outcomes.
- Scheduler only discovers due work and enqueues commands/jobs. It does not contain domain decision logic.
- Every high-risk operation has a dedupe key, trace linkage, and explicit retry policy.
- Observability is part of the baseline, not a follow-up concern.

## Service Topology

### api
Responsibilities:
- validate auth and authorization
- validate input and domain preconditions
- create command rows and job rows in PostgreSQL inside the parent transaction
- enqueue ARQ jobs after commit
- expose status endpoints for command/job inspection

Must not:
- send emails directly
- run batch processors inline
- execute long-running or externally-coupled money/admin operations inside the request path

### worker
Responsibilities:
- consume ARQ jobs
- acquire PostgreSQL ownership of the job before execution
- execute domain-specific handler logic
- record attempts, retries, failures, and final outcome in PostgreSQL
- emit logs, metrics, traces, and alerts

Must not:
- invent business intent
- accept public HTTP traffic

### scheduler
Responsibilities:
- enqueue periodic scans and due jobs
- revive stranded queued jobs after timeout/recovery logic
- drive repeatable operational schedules

Must not:
- contain duplicated business rules already owned by services/handlers

### redis
Responsibilities:
- ARQ transport
- rate limiting backend
- lightweight worker coordination locks if needed

Must not:
- store durable business truth about success, failure, or audit history

### postgres
Responsibilities:
- durable command and job state
- attempt history
- dedupe and replay safety
- audit trail for admin and money operations
- email outbox and domain-ledger truth

## Main Data Model

### background_jobs
Durable record of executable work.

Columns:
- `id uuid primary key`
- `kind text not null`
- `queue_name text not null default 'default'`
- `status text not null`
- `priority smallint not null default 100`
- `dedupe_key text null`
- `payload_json jsonb not null default '{}'::jsonb`
- `scheduled_for timestamptz not null default now()`
- `available_at timestamptz not null default now()`
- `enqueued_at timestamptz null`
- `started_at timestamptz null`
- `finished_at timestamptz null`
- `last_heartbeat_at timestamptz null`
- `last_error text null`
- `last_error_code text null`
- `last_enqueue_error text null`
- `queue_publish_attempts integer not null default 0`
- `attempt_count integer not null default 0`
- `max_attempts integer not null default 5`
- `lock_token uuid null`
- `locked_by text null`
- `trace_id text null`
- `request_id text null`
- `created_by_user_id uuid null`
- `created_by_admin_id uuid null`
- `command_id uuid null`
- `entity_type text null`
- `entity_id uuid null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Allowed statuses:
- `queued`
- `running`
- `succeeded`
- `retry_scheduled`
- `failed`
- `cancelled`
- `dead_letter`

Indexes and constraints:
- partial unique index on `dedupe_key` where status in `('queued', 'running', 'retry_scheduled')`
- index on `(status, scheduled_for)`
- index on `(kind, status, scheduled_for)`
- index on `(command_id)`
- check `attempt_count >= 0`
- check `queue_publish_attempts >= 0`
- check `max_attempts >= 1`

### background_job_attempts
Immutable execution attempt log.

Columns:
- `id uuid primary key`
- `job_id uuid not null references background_jobs(id) on delete cascade`
- `attempt_no integer not null`
- `worker_id text not null`
- `started_at timestamptz not null`
- `finished_at timestamptz null`
- `status text not null`
- `error_code text null`
- `error_text text null`
- `duration_ms integer null`
- `external_ref text null`
- `created_at timestamptz not null default now()`

Indexes and constraints:
- unique `(job_id, attempt_no)`
- index on `(status, created_at)`

### command_requests
Durable business-facing command record created by the API for risky operations.

Columns:
- `id uuid primary key`
- `command_kind text not null`
- `status text not null`
- `dedupe_key text null`
- `requested_by_user_id uuid null`
- `requested_by_admin_id uuid null`
- `request_ip inet null`
- `request_user_agent text null`
- `request_id text null`
- `trace_id text null`
- `payload_json jsonb not null default '{}'::jsonb`
- `result_json jsonb null`
- `error_code text null`
- `error_text text null`
- `submitted_at timestamptz not null default now()`
- `started_at timestamptz null`
- `finished_at timestamptz null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Allowed statuses:
- `accepted`
- `running`
- `succeeded`
- `failed`
- `cancelled`

Indexes and constraints:
- partial unique index on `dedupe_key` where status in `('accepted', 'running')`
- index on `(command_kind, submitted_at desc)`
- index on `(requested_by_admin_id, submitted_at desc)`

### admin_logs
Reuse the existing append-only `admin_logs` table as the audit record for high-risk admin operations.

Required alignment changes:
- add `command_id uuid null references command_requests(id)`
- add `job_id uuid null references background_jobs(id)`
- add `request_id text null`
- add `trace_id text null`
- preserve existing list/history endpoints on top of this table rather than introducing a parallel audit table

### email_outbox
Keep the existing table as the business-facing record for email intent.

Required alignment changes:
- add `command_id uuid null`
- add `job_id uuid null`
- add `dedupe_key text null`
- add `provider_message_id text null`
- add `last_attempt_at timestamptz null`
- add `next_attempt_at timestamptz null`
- keep business-facing statuses compatible with existing code: `pending`, `sent`, `failed`, `suppressed`
- do not overload `email_outbox.status` with background job execution states

Status mapping and coexistence rule:
- `email_outbox.status='pending'` means email intent exists but is not yet durably completed
- `background_jobs.status in ('queued', 'running', 'retry_scheduled')` represents dispatch execution state
- `email_outbox.status='sent'` maps to completed business outcome and normally pairs with `background_jobs.status='succeeded'`
- `email_outbox.status='failed'` means delivery exhausted retries or terminally failed and normally pairs with `background_jobs.status in ('failed', 'dead_letter')`
- old code and new code may coexist during migration only if both preserve the legacy `email_outbox.status` values above

## Job Taxonomy

### Money jobs
- `money.withdrawal.auto_approve`
- `money.withdrawal.reconcile`
- `money.withdrawal.release`
- `money.ledger.repair_check`
- `money.escrow.expiry_scan`

### Email jobs
- `email.outbox.dispatch`
- `email.lifecycle.scan`
- `email.lifecycle.dispatch`
- `email.delivery.reconcile`

### Admin jobs
- `admin.quest.force_complete`
- `admin.quest.force_cancel`
- `admin.wallet.adjust`
- `admin.user.flag_review`
- `admin.notification.broadcast`

### Platform jobs
- `ops.retry_stalled_jobs`
- `ops.prune_old_jobs`
- `ops.prune_old_attempts`
- `ops.prune_old_rate_limit_metrics`

## Command and Job Lifecycle

### API path for async command
1. Endpoint validates auth, input, and business permission.
2. Endpoint opens PostgreSQL transaction.
3. Endpoint inserts `command_requests` row with status `accepted`.
4. Endpoint inserts `background_jobs` row linked to the command.
5. Endpoint writes `admin_logs` when action is admin-originated.
6. Transaction commits.
7. After commit, API attempts ARQ enqueue up to 3 times with short backoff, updates `queue_publish_attempts`, sets `enqueued_at` on success, and records `last_enqueue_error` on failure.
8. If enqueue still fails, API still returns `202 Accepted`; scheduler recovery is the durability backstop and must pick up the orphaned queued job within the recovery SLA.
9. ARQ messages contain only `job_id` plus trace metadata.
10. API returns `202 Accepted` with `command_id`, `job_id`, and status URL.

### Worker path
1. Worker receives `job_id` from ARQ.
2. Worker opens PostgreSQL transaction and atomically claims the job by updating status from `queued` or `retry_scheduled` to `running` with a fresh `lock_token`.
3. Worker inserts a `background_job_attempts` row.
4. Worker executes the handler.
5. On success, worker updates job to `succeeded`, finishes the command if linked, and writes result metadata.
6. On recoverable failure, worker records error, increments attempt count, computes backoff, and moves job to `retry_scheduled` or `dead_letter` if max attempts reached.
7. On terminal business failure, worker marks `failed` without retry and propagates failure to the linked command.

### Scheduler path
1. Scheduler periodically scans for due domain work.
2. Scheduler creates missing command/job rows transactionally where required.
3. Scheduler re-enqueues `retry_scheduled` jobs whose `available_at <= now()`.
4. Scheduler rescues stale `running` jobs whose heartbeat is older than threshold and no active worker ownership can be proven.
5. Rescue reuses the same `job_id`, clears `lock_token`, `locked_by`, and `last_heartbeat_at`, moves the job back to `retry_scheduled`, and never creates a duplicate job row.

## Explicit State Machine

### Phase-1 command shape
In phase 1, every async command maps to exactly one primary background job. Fan-out jobs can be added later, but planning and implementation should assume 1:1 command-to-primary-job linkage.

### command_requests transitions
- `accepted -> running`: when the worker successfully claims the linked primary job
- `running -> succeeded`: when the linked primary job finishes successfully
- `running -> failed`: when the linked primary job finishes terminally failed or reaches `dead_letter`
- `accepted -> cancelled`: only by explicit operator/admin cancellation before worker claim

Rule:
- if a linked background job is in `queued` or `retry_scheduled`, the command remains `accepted`
- if a linked background job is in `running`, the command is `running`
- if a linked background job is in `dead_letter`, the command must be marked `failed`

### background_jobs transitions
- `queued -> running`: worker claim succeeds
- `queued -> cancelled`: explicit operator/admin cancellation before execution
- `running -> succeeded`: handler completes successfully
- `running -> retry_scheduled`: retryable failure
- `running -> failed`: terminal business failure
- `running -> dead_letter`: retry budget exhausted or invariant breach requiring manual intervention
- `retry_scheduled -> running`: worker claim after scheduler re-enqueue
- `retry_scheduled -> cancelled`: explicit operator/admin cancellation

Ownership:
- API creates `accepted` commands and `queued` jobs
- worker drives `running`, `succeeded`, `failed`, `dead_letter`
- scheduler drives re-enqueue and stale-job recovery back to `retry_scheduled`

### Recovery SLA
- API post-commit enqueue failure recovery target: scheduler must rediscover and enqueue orphaned `queued` jobs within 30 seconds
- worker heartbeat interval target: every 15 seconds for long-running jobs
- stale-running threshold: 2 minutes without heartbeat
- alert threshold: any money job stuck in `running` or `retry_scheduled` for more than 5 minutes

## Worker Contract

### ARQ payload
Only pass stable identifiers and metadata needed for trace continuity.

Payload shape:
```json
{
  "job_id": "uuid",
  "trace_id": "optional-trace-id",
  "request_id": "optional-request-id"
}
```

### Handler interface
Each handler must expose:
- `kind`: unique job kind string
- `queue_name`: ARQ queue binding
- `max_attempts`: default retry cap
- `backoff_seconds(attempt_no, error_code) -> int`
- `is_retryable(error) -> bool`
- `execute(conn, payload, context) -> result dict`

### Execution guarantees
- At-least-once delivery at queue level.
- Exactly-once business effect is approximated through idempotent handlers plus PostgreSQL dedupe keys and domain guards.
- Handlers must be safe under replay.

### Required handler behaviors
- fetch domain rows with `FOR UPDATE` when mutating critical money state
- write only through service-layer functions
- update heartbeat for long-running jobs
- classify failures into retryable vs terminal
- never rely on Redis state for correctness

### Transaction isolation
- default worker/job transactions may use normal application isolation when only reading or performing low-risk local mutations
- all money-mutating handlers must use at least `REPEATABLE READ`
- reconciliation, repair, and cross-row ledger correction handlers should use `SERIALIZABLE`

## Dedupe and Idempotency Rules
- Every externally-triggered risky command must carry a deterministic dedupe key.
- Dedupe key examples:
  - withdrawal auto-approve: `withdrawal:auto-approve:{transaction_id}`
  - admin force complete: `admin:force-complete:{quest_id}:{requested_by_admin_id}`
  - email dispatch: `email:{template_key}:{outbox_id}`
- `command_requests.dedupe_key` is the authoritative API replay guard.
- `background_jobs.dedupe_key` is the execution-layer guard against duplicate active work.
- API must return the latest existing command/job when the same dedupe key is resubmitted and the prior command is still in `accepted`, `running`, or `succeeded` within the replay-retention window for that command kind.
- Worker handlers must re-check domain terminal state before making side effects.
- Side effects that touch external providers must store provider reference IDs when available.

### Replay retention
- default replay-retention window for high-risk commands: 24 hours
- money commands may use longer retention where business semantics require it
- dedupe lookup policy belongs to the command kind, not a single global rule

## Retry Policy

### Retry classes
- transient infrastructure errors: retry
- provider/network timeouts: retry
- serialization/deadlock conflicts: retry
- business rule violations: terminal failure, no retry
- invariant violation indicating corruption: terminal failure + alert

### Backoff policy
- default exponential backoff: `30s, 120s, 600s, 1800s, 3600s`
- email dispatch can use smaller early retries
- money jobs use fewer retries but stronger alerting
- dead-letter requires human visibility in admin ops dashboard

## Rate Limit Policy Registry
Current rate limiting exists but policies are distributed across endpoints. The baseline must move to a centralized registry.

### Registry requirements
- single module describing policy per action
- route-scoped admin actions, not one global admin bucket
- support composite limits: IP, user, account, and actor role
- expose policy name for metrics and logs
- fail closed in production when Redis is unavailable
- composite scopes are evaluated independently; a request must pass every configured scope for that policy

### Policy shape
```python
RateLimitPolicy(
    action="admin:POST:/api/v1/admin/quests/{id}/force-complete",
    scopes=["ip", "admin_user"],
    limit=5,
    window_seconds=60,
)
```

### Required baseline policies
- auth register/login/refresh/logout
- wallet withdraw and wallet transaction views
- admin force actions
- admin notification broadcast
- analytics ingest
- public write endpoints

## Observability Baseline

### Logs
- JSON logs for API, worker, and scheduler with consistent fields:
  - `service`
  - `request_id`
  - `trace_id`
  - `job_id`
  - `command_id`
  - `user_id`
  - `admin_id`
  - `job_kind`
  - `attempt_no`
  - `outcome`

### Metrics
- `background_jobs_created_total{kind}`
- `background_jobs_started_total{kind}`
- `background_jobs_succeeded_total{kind}`
- `background_jobs_failed_total{kind,error_code}`
- `background_jobs_dead_letter_total{kind}`
- `background_job_duration_seconds{kind}`
- `background_job_retry_total{kind}`
- `rate_limit_allowed_total{action,scope}`
- `rate_limit_blocked_total{action,scope}`
- `rate_limit_degraded_total{action}`
- `email_outbox_pending_total`
- `money_withdrawal_pending_total`

### Tracing
- propagate `X-Request-ID` and trace context from API to job row and ARQ payload
- start child spans for worker execution and external provider calls
- tag money/admin/email job kinds explicitly

### Alerts
- dead-letter money jobs > 0
- retry-scheduled money jobs older than threshold
- email backlog older than threshold
- Redis unavailable in production
- scheduler heartbeat missing
- worker heartbeat missing

## API Contract Changes

### Async admin commands
High-risk admin endpoints should shift from immediate mutation responses to accepted-command responses.

Response shape:
```json
{
  "command_id": "uuid",
  "job_id": "uuid",
  "status": "accepted",
  "status_url": "/api/v1/admin/commands/{command_id}"
}
```

### Status endpoints
Add read endpoints for:
- command status by id
- job status by id
- admin operations feed filtered by status, action, actor, and time range

### Synchronous exception
Keep low-risk reads and small local actions synchronous. Do not force async for simple CRUD that does not touch money, external systems, or long-running mutation paths.

## Domain Mapping for Phase 1

### Money
- auto-approval of eligible withdrawals moves from standalone script logic into scheduler + worker job handlers
- ledger reconciliation checks become scheduled jobs
- any payout provider integration must run through job handlers, never request path

### Email
- keep `email_outbox` as durable intent table
- dispatch through ARQ workers by job id, not direct batch-only scans
- `email.lifecycle.scan` runs `lifecycle_service` scans and creates or updates `lifecycle_messages`
- `email.lifecycle.dispatch` resolves due `lifecycle_messages`, writes `email_outbox` rows where needed, and then schedules `email.outbox.dispatch`
- `email.outbox.dispatch` performs provider delivery and updates both `email_outbox` and the linked background job

### Admin
- async baseline applies to force-complete, force-cancel, wallet adjustments, broadcasts, and other risky multi-step actions
- admin audit is append-only and linked to both command and job records

## Failure and Recovery Model
- If API writes to PostgreSQL but ARQ enqueue fails after commit, scheduler must find `queued` jobs not present in Redis activity and re-enqueue them.
- If worker crashes mid-job, stale `running` jobs are recovered by scheduler after heartbeat timeout.
- If Redis is lost temporarily, no durable state is lost; processing pauses and resumes after recovery.
- If PostgreSQL is unavailable, API and workers fail fast. No in-memory fallback is allowed for command/job truth.
- command/job rows are append-only operational records and must not be deleted while non-terminal; retention pruning applies only to terminal states past retention windows

## Security Considerations
- admin commands must preserve existing auth, TOTP, and IP allowlist protections
- payload JSON must store only data needed for execution, not raw secrets
- provider credentials stay in settings, never in job payloads
- job inspection endpoints must be admin-only or strictly actor-scoped
- money handlers must preserve Decimal arithmetic and current transaction/audit rules

## Rollout Plan

### Step 1
- add tables and enums/check constraints
- add command/job repository layer
- add ARQ app bootstrap, worker process, scheduler process
- add metrics and heartbeat endpoints for worker/scheduler

### Step 2
- migrate withdrawal auto-approve into the command/job layer
- add money reconciliation job skeletons
- wire admin audit linkage via existing `admin_logs`

Withdrawal cutover rules:
- deploy new scheduler/worker code with withdrawal handlers disabled behind a feature flag
- verify scheduler visibility and dry-run metrics against the current script output
- forbidden legacy process after cutover: `process_withdrawals.py`
- disable `process_withdrawals.py` in cron/task scheduler, Task Scheduler, container command, or process manager before enabling the feature flag
- enable the new withdrawal job path only after confirming no old script instance is running
- run a one-time reconciliation check on pending withdrawals after cutover to verify no rows were skipped or double-processed

### Step 3
- integrate email outbox dispatch through job handlers
- convert lifecycle scans into scheduler-driven jobs

Email migration rules:
- preserve legacy `email_outbox.status` semantics during the whole migration
- first add linking columns and job creation around existing outbox rows without changing delivery semantics
- only then switch dispatch ownership from `process_lifecycle_messages.py` to worker handlers
- retire `process_lifecycle_messages.py` only after backlog parity and retry parity are confirmed

### Step 4
- convert high-risk admin actions to accepted-command pattern
- add admin operations status endpoints and filters

### Step 5
- centralize rate-limit policy registry
- add alerts, backlog views, and dead-letter review flow

## Acceptance Criteria
- Redis outage does not lose accepted commands or queued business work.
- PostgreSQL contains authoritative status for every command and job.
- High-risk admin actions return `202 Accepted` with traceable command/job identifiers.
- Money jobs are idempotent under replay and safe under concurrent worker execution.
- Email delivery is durable, retryable, and observable.
- Scheduler can recover orphaned queued and stale running jobs.
- Rate limiting is policy-driven and route-scoped for admin actions.
- API, worker, and scheduler expose coherent logs, metrics, and traces.

## Implementation Notes
- Reuse existing service-layer business logic where correct; move orchestration, not core rules, into job handlers.
- Keep ARQ messages minimal. PostgreSQL rows are the canonical execution document.
- Prefer additive migrations and compatibility shims so current scripts can be retired gradually rather than broken abruptly.

## Open Decisions For Planning
- final ARQ queue split: single queue vs dedicated `money`, `email`, `admin`, `ops` queues
- exact heartbeat timeout and stale-job reclaim thresholds
- admin UI behavior for long-running commands: polling only vs optional live updates later
- retention windows for attempts, completed jobs, and audit feeds