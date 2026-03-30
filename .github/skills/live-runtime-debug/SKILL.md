---
name: live-runtime-debug
description: 'Debug live-like runtime issues in QuestionWork. Use for worker or scheduler failures, Redis-backed jobs, observability endpoints, health checks, and background runtime triage.'
argument-hint: 'Describe the runtime issue to debug'
---

# Live Runtime Debug

## When to Use
- Worker or scheduler is not processing jobs
- Runtime observability endpoints fail
- Redis or ARQ-backed queues drift from expected state
- Smoke or live verification scripts fail

## Procedure
1. Confirm backend health and readiness first.
2. Inspect worker, scheduler, and queue runtime separately.
3. Use observability endpoints and verification scripts before changing code.
4. Distinguish config errors, dependency outages, and application logic errors.
5. After the fix, rerun the relevant live verification script or smoke check.

## Done Criteria
- Runtime symptom is reproduced or explained
- Fix is verified against the same runtime signal that failed
- Background processing and observability return to expected state
