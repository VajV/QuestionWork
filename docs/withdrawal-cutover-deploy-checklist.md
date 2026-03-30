# Withdrawal Cutover Deployment Checklist

## Before Deploy

- [ ] Confirm the target release includes the trust-layer withdrawal scheduler and worker handler.
- [ ] Confirm the environment has runnable trust-layer `worker` and `scheduler` processes.
- [ ] Identify every legacy launcher of `backend/scripts/process_withdrawals.py`.
- [ ] Remove or disable all cron, Task Scheduler, container command, and process manager entries that launch `process_withdrawals.py`.
- [ ] Verify no currently running process still matches `process_withdrawals.py`.
- [ ] Confirm the rollout operator knows that `process_withdrawals.py` becomes a forbidden process when `WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true`.
- [ ] Confirm observability is available for background jobs, runtime heartbeats, and admin logs.
- [ ] Prepare a small smoke case for one safe pending withdrawal or equivalent validation path.

## During Deploy

- [ ] Enable `WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true` only after the legacy launcher is disabled.
- [ ] Start or restart the trust-layer `worker`.
- [ ] Start or restart the trust-layer `scheduler`.
- [ ] Watch startup output for the guard warning that reminds operators the legacy script is forbidden.
- [ ] Confirm no deployment step or automation attempts to start `process_withdrawals.py`.

## After Deploy

- [ ] Confirm active runtime heartbeats exist for both `worker` and `scheduler`.
- [ ] Confirm new background jobs appear with kind `money.withdrawal.auto_approve`.
- [ ] Confirm a smoke withdrawal is processed by the new job path.
- [ ] Confirm there is no successful run of `process_withdrawals.py` after the feature flag was enabled.
- [ ] Confirm admin/audit linkage is present for the processed withdrawal where expected.
- [ ] Confirm pending withdrawals are not stuck and are not being double-processed.
- [ ] Record the cutover result and any legacy launcher removed from the environment.

Suggested command:

```powershell
cd backend
.venv\Scripts\python.exe scripts/ops_smoke_withdrawal_cutover.py --require-recent-job --require-successful-job --require-audit-linkage
```

## Rollback Trigger Checks

- [ ] Investigate immediately if the legacy guard error appears during normal deploy.
- [ ] Investigate immediately if a pending withdrawal changes state without a corresponding background job.
- [ ] Investigate immediately if both the legacy script and the new job path appear active at the same time.