# QuestionWork Full Project Audit Remediation Plan

Date: 2026-03-19
Status: Draft for execution
Source: Consolidated audit of backend, frontend, security, money flows, jobs/runtime, and migrations

## Executive Summary

The codebase is materially stronger than earlier audit phases, but it is not yet safe to treat as production-ready without another remediation pass. The highest-risk areas are:

1. Financial schema integrity and dispute-path correctness
2. Scheduler and worker safety for background execution
3. WebSocket token exposure and admin/frontend route hardening
4. ORM-to-migration schema drift that can corrupt future autogenerate output

Current launch posture:

- Blockers before production: yes
- Highest-risk domains: wallet, disputes, jobs/runtime, auth transport, schema controls
- Suggested rollout order: money and data integrity first, then runtime safety, then contract cleanup, then backlog hardening

## Confirmed Priority Findings

### P0

1. Financial transactions allow unconstrained `type` values
   - Location: backend/alembic/versions/0a14b7f67d64_init_db.py
   - Risk: invalid ledger semantics and financial data corruption

2. Financial transactions allow unconstrained `status` values
   - Location: backend/alembic/versions/d5e6f7a8b901_week3_economy_core.py
   - Risk: invalid state machine in wallet and withdrawal flows

3. WebSocket access token is transmitted in query string
   - Location: backend/app/api/v1/endpoints/ws.py, frontend/src/hooks/useNotifications.ts
   - Risk: token leakage via logs, browser history, reverse proxies

### P1

1. Partial dispute resolution reads escrow hold without full lock discipline and without currency guard
2. Scheduler has no leader election and can duplicate financial or lifecycle work if multiple instances run
3. Worker can strand jobs in `running` state for up to one hour before rescue
4. Withdrawal auto-approve job lacks strong idempotency guarantees at the job layer
5. Readiness endpoint can return stale success for up to 10 seconds after dependency failure
6. Admin route shell is protected only client-side in Next.js
7. Several DB constraints/indexes exist in migrations but not in ORM metadata, creating autogenerate drift risk
8. Some migrations are operationally irreversible due to placeholder/backfill transforms

### P2

1. Withdrawal runtime limit typed as `str` in numeric comparison
2. Dispute refund path can silently continue if hold record is missing
3. Email job can send successfully while DB status update fails, causing duplicate retry risk
4. Frontend batch withdrawal approval sends unbounded concurrent mutations
5. Frontend has contract drift around wallet totals and admin stats shape
6. Avatar upload validation trusts extension and content type, not file signature
7. `/uploads` is public without auth boundary
8. ORM metadata misses several guild/event/dispute constraints from migrations

## Execution Strategy

### Batch 1: Production Blockers

Priority: P0
Effort: L
Goal: close data-integrity and credential-transport blockers before any broader rollout

Tasks:

1. Run preflight data audit for existing `transactions.type` and `transactions.status` values and backfill or quarantine any invalid rows before adding constraints
2. Add DB-level CHECK constraints for `transactions.type`
3. Add DB-level CHECK constraints for `transactions.status`
4. Replace WebSocket query-token auth with a short-lived Redis-backed WS ticket obtained over authenticated HTTP and sent in the first WebSocket auth message, not in the URL
5. Roll out WS auth with a temporary compatibility window: backend accepts both old and new flows behind a flag, frontend ships the new client flow, then legacy query-token path is removed
6. Update frontend notification socket flow to request the WS ticket before connect and authenticate with an explicit first-frame message
7. Add targeted regression tests for transaction constraint enforcement and WS auth transport

Why first:

- These are direct production blockers with money or credential exposure implications
- They change contracts that later batches should build on instead of working around

Acceptance criteria:

1. Invalid transaction types cannot be inserted through DB or service path
2. Invalid transaction statuses cannot be inserted through DB or service path
3. No access token appears in WebSocket URL construction, server route params, or logs by design
4. WS auth has regression coverage on backend and frontend
5. WS ticket issuance path is rate-limited and security-audited
6. Deployment order and rollback steps are written down for the WS auth cutover

Verification:

1. Backend tests for wallet/disputes/ws pass
2. Manual grep shows no `/ws/...?...token=` pattern in app code
3. Migration applies cleanly on fresh DB and upgrade path DB
4. Compatibility flag can be turned off after frontend rollout without breaking notifications

### Batch 2: Money and Dispute Integrity

Priority: P1
Effort: L
Goal: make dispute and withdrawal paths concurrency-safe and explicit on failure

Tasks:

1. Fix dispute partial-resolution hold lookup to include `FOR UPDATE`
2. Add currency filter to dispute hold lookup
3. Make refund-resolution path fail closed if expected hold is absent
4. Normalize `auto_approve_limit` to `Decimal` at service boundary
5. Review and harden any remaining dispute/wallet silent-continue branches
6. Add regression tests for partial resolution, missing hold, and concurrent dispute resolution attempts

Why this order:

- Batch 1 protects schema and auth transport
- Batch 2 closes the most sensitive remaining financial correctness gaps in request/transaction paths

Acceptance criteria:

1. Concurrent dispute resolution cannot double-release or misapply escrow
2. Missing escrow state raises explicit failure and leaves quest state consistent
3. Auto-approve threshold uses typed money semantics end-to-end

Verification:

1. Targeted pytest for dispute_service, wallet_service, withdrawal_runtime_service
2. Race-oriented tests for repeated or concurrent resolve calls

### Batch 3: Background Runtime Safety

Priority: P1
Effort: XL
Goal: make scheduler and worker safe under duplication, retry, and crash scenarios

Tasks:

1. Add leader election / distributed lock for scheduler
2. Use Redis lease semantics explicitly: `SET key value NX EX ttl`, periodic renewal by the active scheduler, and fenced release only by the owner token
3. Define failover timing: new scheduler may acquire only after lease expiry if renewal stops
4. Add dedupe protection around scheduler-triggered enqueue paths where duplicate execution is unsafe
5. Reduce or redesign stale-running recovery window for jobs
6. Add per-job idempotency or dedupe guarantees for withdrawal auto-approve
7. Improve graceful shutdown handling for in-flight jobs
8. Add retry/backoff guardrails and operational metrics for scheduler failures
9. Review job handlers for post-side-effect crash windows and document exact semantics

Why here:

- These issues are high severity but only express under runtime/process failure or deployment misconfiguration
- They should land after direct financial request-path fixes to reduce moving parts

Acceptance criteria:

1. Multiple schedulers cannot both execute the same scheduled work
2. Worker crash no longer leaves jobs unrescued for one hour
3. Replayed withdrawal approval jobs do not duplicate side effects
4. Scheduler tick failures are observable and do not silently degrade indefinitely
5. Scheduler lease acquisition, renewal, expiry, and failover behavior are covered by tests or deterministic simulation

Verification:

1. Runtime tests for scheduler and worker
2. Fault-injection tests for duplicate scheduler instances
3. Manual smoke against admin runtime endpoints
4. Document handler-specific post-side-effect crash semantics in [docs/plans/2026-03-19-batch3-runtime-crash-semantics.md](docs/plans/2026-03-19-batch3-runtime-crash-semantics.md)

Batch 3 closure notes (2026-03-19):

1. Scheduler lease leadership is now observable through explicit admin heartbeat summary fields, not only raw `meta_json`
2. Live admin runtime verification is restored via `backend/scripts/verify_live_admin_runtime_endpoints.py`
3. Exact replay/crash semantics are documented per registered handler, including the still-open duplicate-delivery risk for `email.send`

### Batch 4: Auth, Admin, and Upload Hardening

Priority: P1/P2
Effort: L
Goal: tighten remaining security surfaces and frontend route protection

Tasks:

1. Add server-side or middleware-level protection for admin pages
2. Implement explicit TOTP setup policy: return setup material only once over authenticated HTTPS, never log raw secret material, never persist it in frontend storage, and require normal admin auth for all post-setup TOTP operations
3. Tighten TOTP verification policy to a documented accepted window and add explicit replay-regression coverage
4. Lock in-memory refresh-token store mutations consistently and document that Redis-backed storage remains mandatory in production
6. Add magic-byte validation for avatar uploads
7. Replace the raw `/uploads` static exposure model with controlled download semantics: authenticated access or signed access for non-public assets, with no unrestricted generic upload mount
8. Narrow CORS dev regex and enforce production-like fail-closed config validation for auth-sensitive environments
9. Reduce readiness cache TTL to explicit production-safe bounds and define failure behavior when Redis or DB is degraded

Acceptance criteria:

1. Admin page HTML is not delivered to unauthorized users by default route path
2. TOTP setup flow has explicit, reviewed behavior for secret transport, replay tolerance, and auditability
3. Refresh token fallback storage cannot race under concurrent requests
4. Upload endpoint rejects spoofed non-image payloads
5. File access policy is explicit and tested with no unrestricted generic user-upload mount remaining
6. Security configuration fails closed in production-like environments
7. Readiness behavior is documented and verified under dependency failure

Verification:

1. Frontend middleware or route-protection tests
2. Backend upload validation tests
3. Manual auth flow smoke including admin TOTP path
4. Targeted tests for refresh-store concurrency and TOTP enforcement behavior
5. Readiness and CORS configuration smoke in production-like env settings

### Batch 5: Schema Drift and Contract Sync

Priority: P1/P2
Effort: XL
Goal: make ORM metadata, migrations, and frontend contract definitions agree so future changes are safe

Tasks:

1. Run preflight drift inventory and list every audited schema item to be synced before editing metadata
2. Mirror missing DB constraints/indexes into ORM metadata
3. Fix nullable/check mismatch for `avg_rating`
4. Preserve critical partial/GIN indexes in ORM declarations
5. Add missing CHECK constraints for template budgets, proposed price, and fee percent where appropriate
6. Remove or isolate migration-time imports of application runtime code where operationally unsafe
7. Convert risky downgrade stories into explicit documented rollback posture for irreversible backfills and destructive transforms
8. Rehearse upgrade safety on both fresh schema and existing snapshots for high-risk migrations
9. Fix frontend type drift around wallet totals and admin stats shape
10. Review backend response models vs frontend normalized types for money fields
11. Add contract tests or snapshot checks for key admin/wallet/dispute payloads

Drift checklist to close in this batch:

1. `events.chk_events_duration` constraint missing from ORM metadata
2. `idx_disputes_quest_active` partial unique index missing from ORM metadata
3. `guild_reward_cards` rarity CHECK missing from ORM metadata
4. `avg_rating` CHECK nullability mismatch between ORM and migration
5. Missing guild and guild_member CHECK constraints in ORM metadata
6. Missing `users.badges` GIN index decision and implementation
7. Missing DB-level checks for `quest_templates.budget`, `applications.proposed_price`, and `quests.platform_fee_percent`
8. Frontend type drift for wallet `total_earned`
9. Frontend type drift for admin user stats shape

Acceptance criteria:

1. Alembic autogenerate does not propose dropping valid production constraints/indexes
2. High-risk migrations have an explicit rollout and rollback posture, even when downgrade cannot fully restore data
3. No migration depends on fragile runtime-only application behavior without explicit justification
4. Frontend types match backend payload shapes for audited endpoints
5. Financial numeric fields are consistently modeled and normalized
6. Every item in the drift checklist is either fixed, explicitly deferred, or proven not applicable

Verification:

1. Alembic autogenerate dry run reviewed manually
2. TypeScript compile remains clean
3. Targeted contract tests pass
4. Upgrade rehearsal on fresh DB and existing snapshot succeeds

### Batch 6: Reliability and UX Cleanup

Priority: P2/P3
Effort: L
Goal: remove remaining operational and UX rough edges that increase support load or mask failures

Tasks:

1. Fix frontend batch approval throttling / sequencing
2. Fix quest detail fetch cancellation race
3. Improve WebSocket reconnect behavior on frontend
4. Expose non-silent error state in world meta and similar hooks
5. Add explicit warning/error logging for swallowed Redis publish failures in notification push paths
6. Make email outbox delivery semantics explicit so successful SMTP delivery cannot be retried indefinitely after DB status failure
7. Make backend WebSocket behavior explicit under Redis/DB outage by closing degraded connections with observable failure semantics

Acceptance criteria:

1. Admin bulk actions do not hammer the API uncontrollably
2. Frontend screens do not render stale data after racing requests
3. Real-time delivery degrades observably, not silently
4. Backend realtime paths fail explicitly under dependency outage instead of hanging invisibly

## Audit Scope Resolution Map

This section maps audited domains to remediation outcome so the full-project audit can be closed explicitly.

1. Wallet, withdrawals, escrow, disputes
   - Outcome: remediation required
   - Batches: 1, 2, 3, 5

2. Auth, JWT, refresh, TOTP, admin security
   - Outcome: remediation required
   - Batches: 1, 4

3. Jobs, scheduler, worker, runtime heartbeat, admin runtime
   - Outcome: remediation required
   - Batches: 3, 6

4. Frontend contract safety and protected routes
   - Outcome: remediation required
   - Batches: 1, 4, 5, 6

5. Migrations, schema controls, ORM drift
   - Outcome: remediation required
   - Batch: 5

6. Guild economy and progression
   - Outcome: no launch blocker found, but bookkeeping and schema-hardening follow-up remains
   - Batches: 5, 6

7. Leads, lifecycle, and analytics side effects
   - Outcome: no new P0/P1 found in this pass; keep under regression coverage and include in post-remediation re-audit
   - Batch: none for immediate blockers

8. Notifications and realtime delivery
   - Outcome: remediation required for degradation visibility and WS transport contract
   - Batches: 1, 6

9. Uploads and avatar handling
   - Outcome: remediation required
   - Batch: 4

10. Infra, health, readiness, environment fail-safe behavior
   - Outcome: remediation required
   - Batches: 3, 4

Verification:

1. Frontend interaction smoke tests
2. Hook/component tests where present
3. Runtime logs show actionable warnings for degraded push paths

## Dependency Order

1. Batch 1 before all others
2. Batch 2 before Batch 3 if the same wallet/dispute tables are touched
3. Batch 4 can run partially in parallel with Batch 3 except for WS contract work, which depends on Batch 1
4. Batch 5 should start only after Batch 1 and Batch 2 stabilize backend contracts
5. Batch 6 should land last unless a cleanup item is required to support another batch's tests

## Suggested Task Decomposition For Subagent Execution

Use one task per independently reviewable change set:

1. Enforce transaction ledger constraints
2. Replace WebSocket query-token auth
3. Fix dispute escrow locking and failure semantics
4. Normalize withdrawal auto-approve amount typing
5. Add scheduler leader election
6. Harden worker crash recovery and shutdown
7. Make withdrawal auto-approve idempotent
8. Add server-side admin route protection
9. Harden TOTP setup, replay policy, and refresh-store concurrency
10. Harden avatar upload and uploads access model
11. Tighten readiness and CORS fail-closed behavior
12. Sync ORM constraints/indexes with migrations
13. Make high-risk migrations rollout-safe and document rollback posture
14. Sync frontend wallet/admin contracts
15. Fix frontend bulk action and fetch race issues
16. Make realtime degradation observable on backend and frontend

Each task should follow:

1. Implementer subagent
2. Spec review
3. Code quality review
4. Regression verification

## Minimal Verification Matrix

Backend:

1. `pytest tests/test_wallet_service.py`
2. `pytest tests/test_withdrawal_runtime_service.py`
3. `pytest tests/test_dispute_service.py`
4. `pytest tests/test_job_runtime.py`
5. `pytest tests/test_scheduler_runtime.py`
6. `pytest tests/test_admin_runtime_service.py`
7. `pytest tests/test_ws_endpoints.py`

Frontend:

1. `npx tsc --noEmit`
2. Admin route guard smoke
3. Notification socket smoke
4. Withdrawal admin flow smoke

Schema / infra:

1. Alembic upgrade on fresh DB
2. Alembic upgrade on existing DB snapshot
3. Autogenerate drift inspection
4. Runtime health/readiness smoke

## Exit Criteria For Production Readiness Recheck

The next full re-audit should only be considered launch-ready if:

1. All Batch 1 and Batch 2 items are closed
2. Batch 3 leader election and job idempotency are closed for any multi-instance deployment
3. No token-bearing query-string auth remains in app flows
4. Alembic autogenerate shows no dangerous drift against intended schema
5. Admin, wallet, dispute, runtime, and WS regression suites pass
6. Frontend TypeScript remains clean and contract mismatches are resolved