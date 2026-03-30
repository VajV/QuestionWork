# Withdrawal Auto-Approve Cutover Runbook

## Purpose

This runbook describes the operational rules for the withdrawal auto-approve cutover from the legacy script path to the trust-layer `worker` + `scheduler` job path.

## Scope

This applies when the feature flag below is enabled:

```env
WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true
```

## Ownership After Cutover

When `WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true`, withdrawal auto-approval is owned by:

- the trust-layer `scheduler`
- the trust-layer `worker`

The legacy script no longer owns this workflow.

## Forbidden Legacy Process

Forbidden process after cutover:

- `backend/scripts/process_withdrawals.py`

This means the following must be disabled before the feature flag is enabled:

- cron entries
- Windows Task Scheduler tasks
- container startup commands
- process manager entries
- ad-hoc operator commands that still launch `process_withdrawals.py`

If the legacy script is started while the flag is enabled, it now fails immediately with this guard message:

```text
process_withdrawals.py must not run while WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true. Disable the legacy cron/task before using the new withdrawal job path.
```

## Required Rollout Sequence

1. Deploy code containing the trust-layer withdrawal handler and scheduler support.
2. Confirm the new `worker` and `scheduler` processes are available to run in the target environment.
3. Disable every legacy launcher for `process_withdrawals.py`.
4. Verify no active `process_withdrawals.py` instance is still running.
5. Enable `WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true`.
6. Start or restart the trust-layer `worker` and `scheduler`.
7. Run a small smoke on a safe pending withdrawal or dry-run validation path.
8. Verify pending withdrawals are being handled by `money.withdrawal.auto_approve` jobs, not by the legacy script.

## Verification Signals

Expected signals after cutover:

- runtime heartbeats show active `worker` and `scheduler`
- withdrawal jobs are created with kind `money.withdrawal.auto_approve`
- admin logs link to the new job path metadata where applicable
- no process list entry remains for `process_withdrawals.py`

Unexpected signals that require rollback or investigation:

- any scheduler, cron, or task runner still starts `process_withdrawals.py`
- pending withdrawals are changing state without corresponding background jobs
- the legacy guard error appears during normal deployment, which means an old launcher still exists

## Short Ops Smoke

Use the short smoke script after deploy to automate the most important post-cutover checks.

Run from `backend/`:

```powershell
.venv\Scripts\python.exe scripts/ops_smoke_withdrawal_cutover.py --require-recent-job --require-successful-job --require-audit-linkage
```

What it checks:

- backend health is reachable
- admin auth works
- active runtime heartbeats include both `worker` and `scheduler`
- no local `process_withdrawals.py` process is still running
- recent `money.withdrawal.auto_approve` jobs exist
- at least one recent withdrawal job succeeded
- at least one recent successful withdrawal job has `admin_logs.job_id` linkage

If you only want the lightweight baseline without requiring a recent processed withdrawal yet, run:

```powershell
.venv\Scripts\python.exe scripts/ops_smoke_withdrawal_cutover.py
```

## Operator Notes

- The guard is intentional. Treat it as a deployment misconfiguration signal, not as an application bug.
- Do not silence or bypass the guard. Remove the legacy launcher instead.
- Keep the worker and scheduler logs available during the first rollout window so ownership is easy to confirm.