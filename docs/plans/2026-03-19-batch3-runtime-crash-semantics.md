# Batch 3 Runtime Crash Semantics

Date: 2026-03-19
Scope: current trust-layer worker execution path, registered job handlers, and admin runtime observability expectations

## Execution Boundary

Every background job currently has three distinct phases:

1. Claim phase in `worker.execute_job_payload()`
   - The worker claims the job, marks the command `running`, writes a worker heartbeat row, and inserts an attempt row before the handler executes.
2. Handler phase in `handler.execute()`
   - This is where business side effects happen.
   - Some handlers wrap all DB side effects in a single SQL transaction.
   - Some handlers perform an external side effect first and only then update DB state.
3. Terminal bookkeeping phase in `worker.execute_job_payload()`
   - After the handler returns, the worker separately updates `background_jobs` and then `command_requests`.

The important implication is that handler-side effects and worker-side terminal state updates are not one atomic unit today.

## Exact Post-Side-Effect Semantics

### `ops.noop`

- External side effects: none.
- Crash before handler return:
  - No business side effect has happened.
  - The job may remain `running` until rescued.
- Crash after handler return but before `mark_job_succeeded()`:
  - Still no external side effect duplication risk.
  - Replay is safe and only repeats the no-op result generation.

### `money.withdrawal.auto_approve`

- Side effects inside one SQL transaction:
  - `admin_service.approve_withdrawal(...)`
  - `notification_service.create_notification(...)`
- Crash before the transaction commits:
  - PostgreSQL rolls back the withdrawal approval and notification insert.
  - Replay re-runs the approval path once the job is rescued.
- Crash after the transaction commits but before `mark_job_succeeded()`:
  - Withdrawal approval and notification are already durable.
  - The job row may still look `running` until rescue.
  - Replay is intentionally non-destructive because the handler re-locks the transaction row and returns `ignored` when withdrawal status is no longer `pending`.
  - Result: no duplicate approval and no duplicate approval-notification from this handler path.
- Crash after `mark_job_succeeded()` but before `mark_command_succeeded()`:
  - Job can already be `succeeded` while the linked command still looks `running`.
  - This is a state skew, not a duplicate money movement.

### `event_finalize`

- Side effects inside one SQL transaction via `event_service.finalize_event(...)`:
  - leaderboard inserts
  - badge awards
  - XP and stat updates
  - notifications
  - event status update to `finalized`
- Crash before the transaction commits:
  - All event finalization changes roll back together.
- Crash after the transaction commits but before `mark_job_succeeded()`:
  - Event finalization is already durable.
  - Replay re-enters `finalize_event()` and returns `already_finalized=True` because the event row is locked and status-checked.
  - Result: duplicate XP, badge, and leaderboard writes are prevented by the finalized status guard plus `ON CONFLICT DO NOTHING` on badge/leaderboard inserts.
- Crash after `mark_job_succeeded()` but before `mark_command_succeeded()`:
  - Same command/job skew risk as other handlers remains.

### `email.send`

- Side effects are not atomic today.
- Order is:
  1. external SMTP send via `_deliver(...)`
  2. DB update `email_outbox.status='sent'`
- Crash before SMTP send:
  - No email leaves the system.
  - Replay will attempt normal delivery.
- Crash after SMTP send but before the DB update to `sent`:
  - The email may already be delivered externally.
  - The outbox row still looks `pending`.
  - Replay can send the same email again.
  - This remains the one registered handler with known duplicate-delivery exposure after a post-side-effect crash.
- Crash after the outbox row is updated but before `mark_job_succeeded()`:
  - Email outbox state is durable as `sent`.
  - Replay returns `ignored` because the row is no longer `pending`.
  - Result: duplicate delivery is avoided in this narrower window.

## Rescue Window Semantics

- Worker heartbeat interval is 15 seconds.
- Scheduler stale-running recovery window is intentionally capped to 45 seconds.
- Practical meaning:
  - A crashed worker can strand a `running` job for about 45 seconds instead of the previous one-hour ceiling.
  - Replay after rescue is safe for `ops.noop`, `money.withdrawal.auto_approve`, and `event_finalize`.
  - Replay after rescue can duplicate `email.send` if the crash happened after SMTP delivery but before DB state was advanced.

## Admin Endpoint Interpretation

- `/api/v1/admin/runtime/heartbeats` now exposes explicit leadership and freshness fields rather than requiring operators to infer them from raw `meta_json`.
- `leader_runtime_id` and `leader_count` are the primary signals for scheduler lease health.
- `active_workers` and `active_schedulers` summarize non-stale runtimes by kind.
- Per-runtime `lease_expires_in_seconds` shows how close a scheduler heartbeat is to losing its observed lease window.
- Per-runtime `queue_name` identifies the active worker queue without requiring consumers to parse `meta_json`.

## Known Remaining Gap

- Command/job terminal updates are still separate writes after handler completion.
- That means a crash can still leave `background_jobs.status='succeeded'` while `command_requests.status='running'` until an operator or a later reconciliation step inspects it.
- This Batch 3 closure documents that behavior explicitly; it does not yet add a reconciler for terminal command/job skew.