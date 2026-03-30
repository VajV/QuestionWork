# Production Audit Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Закрыть все подтверждённые findings из последнего production audit так, чтобы release confidence на critical quest flow восстановился, infra/readiness semantics стали честными, schema truth совпала с миграциями, а frontend money contract перестал расходиться с backend wire format.

**Architecture:** Выполнять работу в четыре очереди. Сначала восстановить доверие к релизному safety net вокруг `confirm_quest_completion`, потому что сейчас красный regression suite делает любые последующие фиксы ненадёжными. Затем выровнять backend operational contracts: readiness/Redis semantics, ORM schema truth и proxy-aware rate limiting. После этого убрать frontend contract drift по денежным полям и только в конце зачистить низкорисковые warnings и выполнить полный verification pass.

**Tech Stack:** FastAPI, asyncpg, PostgreSQL, Redis, Alembic, pytest, Next.js 14 App Router, React 18, TypeScript, npm build.

---

## Краткое описание подтверждённых проблем

### 1. P1: Красный regression suite на критическом quest completion flow

`backend/tests/test_audit_p0p1_fixes.py` уже не соответствует текущему runtime path: `confirm_quest_completion()` теперь вызывает `guild_economy_service.apply_quest_completion_rewards()`, а тестовые mock sequence всё ещё моделируют старый поток. Пока этот suite красный, release gate по XP/stat/payout path нельзя считать рабочим.

### 2. P2: `/ready` сообщает готовность при degraded Redis semantics

Сейчас readiness делает Redis обязательным только в узкой ветке `production + ADMIN_TOTP_REQUIRED`, хотя refresh tokens, rate limits и admin TOTP replay protection уже завязаны на Redis/shared state semantics. Это даёт operational contract gap между “pod ready” и фактическим поведением auth/abuse controls.

### 3. P2: ORM и Alembic расходятся по `transactions.user_id`

Миграция уже перевела `transactions.user_id` в nullable + `ON DELETE SET NULL`, чтобы сохранять финансовую историю при удалении пользователя. `TransactionORM` до сих пор описывает старую схему с `nullable=False` и `ON DELETE CASCADE`, что создаёт ложный источник истины для autogenerate и code review.

### 4. P2: Marketplace mutations обходят trusted-proxy IP resolution

`create_guild`, `join_guild`, `leave_guild` берут `request.client.host` напрямую, хотя остальной backend использует `get_client_ip()` с trusted proxy rules. За reverse proxy это даёт неправильный rate-limit bucket и несогласованную антиабьюз-политику.

### 5. P2: Frontend money contract всё ещё “number-first”, а backend wire format остаётся Decimal-like

Backend сериализует денежные значения через Decimal-aware response layer, а frontend shared types фиксируют `MoneyAmount = number` и часть полей напрямую типизируют как `number`. Сейчас это partly masked центральной нормализацией в `src/lib/api.ts`, но wire contract и TS contract по-прежнему расходятся.

### 6. P3: Marketplace pages оставляют React hook dependency warnings

`npm run build` проходит, но предупреждения по `exhaustive-deps` остаются. Это не production blocker, но это реальный сигнал о хрупком fetch/state lifecycle, который лучше закрыть после основных correctness fixes.

## Execution Rules

1. Работать строго по batch order. Не исправлять frontend contract до восстановления backend regression signal.
2. Для каждого behavior fix сначала писать или чинить тест, потом править код, потом прогонять точечную проверку.
3. Один task = один commit. Не смешивать readiness, schema drift и frontend contract в одном diff.
4. Не рефакторить соседние модули без прямой связи с текущим finding.
5. После каждой итерации прогонять только минимально достаточные проверки, а в финале сделать общий verification sweep.

## Batch Order

1. Release Confidence Recovery
2. Infra / Schema Correctness
3. Frontend Contract Cleanup
4. Low-Risk Cleanup + Final Verification

---

## Batch 1: Restore Release Confidence On Quest Completion

Цель batch: вернуть зелёный и полезный regression suite для `confirm_quest_completion`, чтобы последующие фиксы не шли вслепую.

### Task 1: Reproduce and document the exact failing quest-completion regressions

**Files:**
- Check: `backend/tests/test_audit_p0p1_fixes.py`
- Check: `backend/app/services/quest_service.py`
- Check: `backend/app/services/guild_economy_service.py`

**Step 1: Run the currently failing tests**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_audit_p0p1_fixes.py -q --tb=short -k "burnout or stats_capped"`

Expected: FAIL with `StopAsyncIteration` in `test_burnout_reduces_xp_reward` and `test_stats_capped_at_100_on_completion`.

**Step 2: Capture the live runtime path before changing tests**

Trace which extra DB calls and service hooks now occur after:
- burnout check;
- XP/stat updates;
- `wallet_service.split_payment(...)`;
- `guild_economy_service.apply_quest_completion_rewards(...)`;
- badge/notification/message/class XP side effects.

**Step 3: Write a short note in the PR/commit description**

Document that the failure is stale test scaffolding, not yet proof of broken production behavior.

**Step 4: Commit nothing yet**

No commit at this task. This step only freezes evidence.

### Task 2: Update the two stale audit tests to match the current completion pipeline

**Files:**
- Modify: `backend/tests/test_audit_p0p1_fixes.py`
- Check: `backend/app/services/quest_service.py`

**Step 1: Rewrite the failing test setup**

Adjust mocks so the two tests explicitly stub:
- `guild_economy_service.apply_quest_completion_rewards(...)`;
- any extra `fetchrow` / `fetchval` calls introduced by the new flow;
- side effects unrelated to the invariant under test.

The assertions must still focus on the real behavior under test:
- burnout reduces XP reward;
- stats never exceed `STAT_CAP`.

**Step 2: Run the two tests to verify they still fail for the right reason if assertions are broken**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_audit_p0p1_fixes.py -q --tb=short -k "burnout or stats_capped"`

Expected: Either PASS after the scaffolding fix, or fail only on business assertions rather than `StopAsyncIteration`.

**Step 3: Apply the minimal test fix**

Do not weaken assertions into “service was called”. Keep invariant assertions on XP/stat outputs or update SQL arguments.

**Step 4: Re-run the two tests**

Expected: PASS.

**Step 5: Commit**

`git add backend/tests/test_audit_p0p1_fixes.py`

`git commit -m "test: align quest completion audit regressions with guild hooks"`

### Task 3: Add one integration-style guard for quest completion with guild side effects enabled

**Files:**
- Modify: `backend/tests/test_quest_service.py`
- Check: `backend/app/services/quest_service.py`
- Check: `backend/app/services/guild_economy_service.py`

**Step 1: Write the failing test**

Add a focused test that executes `confirm_quest_completion()` with guild economy hooks stubbed at the boundary and verifies:
- quest reaches `confirmed`;
- payout split is triggered;
- guild completion rewards hook is invoked exactly once;
- XP/stat outputs remain deterministic.

**Step 2: Run the test and verify it fails**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_quest_service.py -q --tb=short -k "confirm_quest_completion and guild"`

Expected: FAIL until the new regression test is correctly wired.

**Step 3: Write minimal implementation if test setup exposes missing seam**

If the test is impossible without brittle mock sequencing, introduce the smallest seam necessary inside `quest_service.py` for stubbing downstream side effects cleanly.

**Step 4: Re-run the targeted quest service tests**

Expected: PASS.

**Step 5: Commit**

`git add backend/tests/test_quest_service.py backend/app/services/quest_service.py`

`git commit -m "test: cover quest confirmation with guild reward side effects"`

### Batch 1 exit criteria

- `tests/test_audit_p0p1_fixes.py` is green.
- Quest completion regressions fail only on real invariant breakage, not stale mock plumbing.
- At least one non-trivial test covers completion flow plus guild side effects.

---

## Batch 2: Infra And Schema Correctness

Цель batch: убрать backend contract drift между readiness, Redis usage и schema truth.

### Task 4: Formalize readiness expectations for Redis-backed shared state

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_readiness.py`
- Check: `backend/app/core/security.py`
- Check: `backend/app/core/ratelimit.py`
- Check: `backend/app/api/deps.py`

**Step 1: Write the failing tests**

Add tests for `/ready` covering at least these cases:
- DB ok, Redis ok => ready;
- DB ok, Redis degraded, shared-state-required mode => not ready;
- DB ok, Redis degraded, explicitly allowed degraded-local mode => ready but with machine-readable degraded state.

**Step 2: Run the tests and verify they fail**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_readiness.py -q --tb=short`

Expected: FAIL because the test file or required readiness contract does not exist yet.

**Step 3: Implement the minimal readiness contract**

Choose one explicit policy and encode it in code:
- either Redis is required for all non-development environments;
- or readiness exposes a dedicated degraded mode when local-memory fallbacks are allowed.

The output must let deploy orchestration distinguish true shared-state readiness from degraded single-process fallback.

**Step 4: Re-run the readiness tests**

Expected: PASS.

**Step 5: Commit**

`git add backend/app/main.py backend/tests/test_readiness.py`

`git commit -m "fix: make readiness reflect redis shared-state semantics"`

### Task 5: Align `TransactionORM` with the live migrated schema

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/tests/test_integration.py` or `backend/tests/test_admin_service.py`
- Check: `backend/alembic/versions/v7w8x9y0z1a2_audit_preserve_and_revision_count.py`

**Step 1: Write the failing schema-truth test**

Add a metadata-level or migration-aware assertion that `TransactionORM.user_id` is:
- nullable;
- `ON DELETE SET NULL`.

If there is no good existing place, add a focused assertion in `backend/tests/test_admin_service.py` around delete-user preservation semantics.

**Step 2: Run the targeted test and verify it fails**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_admin_service.py -q --tb=short -k "delete_user or transaction"`

Expected: FAIL or require new assertion because ORM metadata still reflects the old shape.

**Step 3: Apply the minimal model fix**

Update `TransactionORM.user_id` so the ORM matches the already-shipped Alembic behavior.

**Step 4: Re-run the targeted test**

Expected: PASS.

**Step 5: Validate no spurious schema drift remains**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m alembic check`

Expected: PASS, or at minimum no diff for `transactions.user_id`.

**Step 6: Commit**

`git add backend/app/db/models.py backend/tests/test_admin_service.py`

`git commit -m "fix: align transaction orm metadata with preserved audit schema"`

### Task 6: Make marketplace mutations proxy-aware like the rest of the API

**Files:**
- Modify: `backend/app/api/v1/endpoints/marketplace.py`
- Modify: `backend/tests/test_ratelimit.py`
- Optional: Modify: `backend/tests/test_endpoints.py`

**Step 1: Write the failing endpoint-level test**

Add a regression case proving that marketplace mutation endpoints use the same IP resolution contract as auth/admin endpoints when `TRUSTED_PROXY_CIDRS` is configured.

**Step 2: Run the test and verify it fails**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_ratelimit.py -q --tb=short -k "marketplace or trusted_proxy"`

Expected: FAIL until marketplace routes are switched to `get_client_ip()`.

**Step 3: Apply the minimal implementation**

Replace direct `request.client.host` reads in:
- `create_guild`;
- `join_guild`;
- `leave_guild`;

with the shared helper from `app.core.ratelimit`.

**Step 4: Re-run targeted tests**

Expected: PASS.

**Step 5: Commit**

`git add backend/app/api/v1/endpoints/marketplace.py backend/tests/test_ratelimit.py`

`git commit -m "fix: use trusted proxy ip resolution for marketplace mutations"`

### Batch 2 exit criteria

- `/ready` truthfully reflects Redis dependency mode.
- ORM metadata matches the migrated DB contract.
- Marketplace rate limits use the same proxy-aware IP semantics as the rest of the API.

---

## Batch 3: Frontend Money Contract Cleanup

Цель batch: убрать ложный `number`-first contract и сделать работу с деньгами явно нормализованной на границе API.

### Task 7: Inventory every shared money type that still claims raw `number`

**Files:**
- Modify: `frontend/src/types/index.ts`
- Check: `frontend/src/lib/api.ts`
- Check: `frontend/src/app/admin/withdrawals/page.tsx`
- Check: `frontend/src/app/marketplace/page.tsx`

**Step 1: Freeze current mismatches in a checklist comment or task note**

List all known fields such as:
- `MoneyAmount = number`;
- transaction `amount: number`;
- wallet `balance`, `new_balance`, `total_earned`;
- any admin/reporting money fields still typed as numeric at the wire layer.

**Step 2: Do not commit yet**

This task is preparation for the next two tasks.

### Task 8: Separate wire types from normalized UI types

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Write the failing type-level or unit-style checks**

If the project has no frontend unit test harness, use TypeScript as the gate by introducing explicit wire-vs-normalized interfaces that cause compile errors until wrappers are updated.

Examples of the intended split:
- wire type: `type DecimalString = string` or `type MoneyWire = string`;
- normalized UI type: `type MoneyAmount = number` only after `toNumber()` conversion;
- wrapper return types from `fetchApi()` should return normalized shapes, not raw wire shapes.

**Step 2: Run type-check/build to verify the mismatch surfaces**

Run: `Set-Location c:\QuestionWork\frontend; npm run build`

Expected: FAIL or require code updates where UI still assumes the old shared type contract.

**Step 3: Apply the minimal contract split**

Keep one explicit normalization seam in `src/lib/api.ts`.
Do not spread ad hoc `Number(...)` conversions into components.

**Step 4: Re-run the frontend build**

Expected: PASS.

**Step 5: Commit**

`git add frontend/src/types/index.ts frontend/src/lib/api.ts`

`git commit -m "refactor: separate money wire types from normalized frontend models"`

### Task 9: Remove remaining direct money-type assumptions from consumer screens

**Files:**
- Modify: `frontend/src/app/admin/withdrawals/page.tsx`
- Modify: `frontend/src/app/marketplace/page.tsx`
- Modify: any other touched consumers reported by the build

**Step 1: Fix the smallest set of build errors or contract mismatches**

Update consumer code so components only consume normalized fields returned by `src/lib/api.ts`.

**Step 2: Re-run the frontend build**

Run: `Set-Location c:\QuestionWork\frontend; npm run build`

Expected: PASS.

**Step 3: Commit**

`git add frontend/src/app/admin/withdrawals/page.tsx frontend/src/app/marketplace/page.tsx`

`git commit -m "fix: consume normalized money values in frontend screens"`

### Batch 3 exit criteria

- Wire contract and UI contract are no longer conflated.
- `src/lib/api.ts` is the single money normalization boundary.
- Frontend build is green after the contract cleanup.

---

## Batch 4: Cleanup And Final Verification

Цель batch: закрыть low-priority warning debt и доказать, что все remediation batches действительно совместимы друг с другом.

### Task 10: Clear the marketplace hook dependency warnings

**Files:**
- Modify: `frontend/src/app/marketplace/page.tsx`
- Modify: `frontend/src/app/marketplace/guilds/[slug]/page.tsx`

**Step 1: Reproduce warnings**

Run: `Set-Location c:\QuestionWork\frontend; npm run build`

Expected: WARN on `react-hooks/exhaustive-deps` in the two marketplace pages.

**Step 2: Apply the minimal fix**

Make effect dependencies explicit by stabilizing loader functions or inlining effect logic. Do not add gratuitous memoization.

**Step 3: Re-run the build**

Expected: PASS with no exhaustive-deps warnings.

**Step 4: Commit**

`git add frontend/src/app/marketplace/page.tsx frontend/src/app/marketplace/guilds/[slug]/page.tsx`

`git commit -m "fix: resolve marketplace hook dependency warnings"`

### Task 11: Run the final verification sweep

**Files:**
- No code changes expected unless verification exposes a real regression

**Step 1: Run backend targeted regression suite**

Run: `Set-Location c:\QuestionWork\backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security.py tests/test_wallet_service.py tests/test_admin_service.py tests/test_audit_p0p1_fixes.py tests/test_quest_service.py tests/test_ratelimit.py tests/test_config_validation.py -q --tb=short`

Expected: PASS.

**Step 2: Run frontend build**

Run: `Set-Location c:\QuestionWork\frontend; npm run build`

Expected: PASS with no marketplace hook warnings.

**Step 3: Run git diff review**

Run: `Set-Location c:\QuestionWork; git status --short`

Expected: only the intended remediation files are modified.

**Step 4: Commit**

If verification required no extra code changes, no additional commit is needed.
If one small verification fix was required, commit it separately with a message scoped to the actual regression.

### Batch 4 exit criteria

- Backend targeted regressions pass.
- Frontend build passes cleanly.
- No unresolved findings remain from the latest audit except intentionally deferred backlog items.

---

## Risks And Guardrails During Execution

### Guardrail 1: Do not re-open already-closed admin money issues

The latest audit re-validated that:
- `admin_service.update_quest` now blocks financial mutations after assignment/escrow;
- `admin_service.force_complete_quest` now requires an active hold.

Do not broaden this plan back into old already-closed admin payout fixes unless new evidence appears during implementation.

### Guardrail 2: Do not let test fixes become assertion weakening

For Batch 1, changing mocks is allowed; deleting or diluting invariant assertions is not.

### Guardrail 3: Keep one normalization boundary on the frontend

For Batch 3, do not spread money parsing into pages/components. The API layer remains the seam.

### Guardrail 4: Readiness semantics must be explicit, not magical

If degraded Redis mode remains allowed outside development, encode and document it as a first-class state rather than hiding it behind `ready: true` with ambiguous checks.

---

## Suggested Commit Sequence

1. `test: align quest completion audit regressions with guild hooks`
2. `test: cover quest confirmation with guild reward side effects`
3. `fix: make readiness reflect redis shared-state semantics`
4. `fix: align transaction orm metadata with preserved audit schema`
5. `fix: use trusted proxy ip resolution for marketplace mutations`
6. `refactor: separate money wire types from normalized frontend models`
7. `fix: consume normalized money values in frontend screens`
8. `fix: resolve marketplace hook dependency warnings`

---

## Final Success Criteria

- Release confidence on quest completion is restored by green targeted regressions.
- Redis/shared-state behavior is accurately represented in readiness output.
- ORM metadata no longer lies about transaction preservation semantics.
- Marketplace mutation throttling is proxy-safe.
- Frontend money handling has an explicit wire-to-UI contract.
- Frontend build is clean and warning-free for the audited marketplace pages.
