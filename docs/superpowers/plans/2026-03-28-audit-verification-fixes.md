# Audit Verification Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the confirmed audit issues in QuestionWork without spending time on disproven claims.

**Architecture:** This plan is intentionally split into narrow backend and frontend tracks. The backend work fixes root-cause cache invalidation and data-retention behavior. The frontend work restores the intended LazyMotion bundle pattern and moves the heaviest manual profile-style loaders onto the existing SWR helper.

**Tech Stack:** FastAPI, asyncpg, PostgreSQL, Redis, Next.js App Router, TypeScript, Framer Motion, pytest, ESLint, TypeScript compiler.

---

I'm using the writing-plans skill to create the implementation plan.

## Verified Scope

Confirmed issues this plan covers:
- Overly broad cache invalidation for user- and guild-scoped cached reads.
- No retention strategy for `analytics_events`, so table growth is unbounded.
- `LazyMotion` is present, but many frontend files still import `motion` directly from `framer-motion`.
- `useSWRFetch` exists, but high-traffic authenticated pages still use manual `useEffect` loading.

Explicitly excluded from this plan because the claim did not hold during code review:
- Multi-worker WebSocket message loss. Notifications and chat already publish through Redis Pub/Sub.
- Email outbox lacking `FOR UPDATE SKIP LOCKED`. It is already present in the delivery path.
- `quest_service.list_quests` N+1 for applications. It already batch-loads application rows.
- Badge catalogue missing cache. It is already cached.
- WebSocket connections permanently holding DB pool slots. Current WS handlers acquire DB connections only for short checks.

Strategic debt, but not treated as a current defect here:
- FastAPI pinned to 0.109.0.
- No `uvloop` production path.

## Phase Execution Order

This remediation is intentionally split into 3 sequential phases.

- **Phase 1 — Cache Integrity:** fix over-broad invalidation so cached read paths stop evicting unrelated user and guild entries.
- **Phase 2 — Backend Retention Safety:** add bounded retention for `analytics_events` so operational growth is controlled.
- **Phase 3 — Frontend Runtime Cleanup:** restore LazyMotion value and move the heaviest authenticated pages to the existing SWR fetch model.

Execution rule: implement exactly one phase at a time, validate it, then stop for review before starting the next phase.

## Phase 1: Cache Integrity

### Task 1: Scope Cache Keys Before Invalidating

**Files:**
- Modify: `backend/app/core/cache.py`
- Modify: `backend/app/services/review_service.py`
- Modify: `backend/app/services/class_service.py`
- Modify: `backend/app/services/guild_progression_service.py`
- Modify: `backend/app/services/marketplace_service.py`
- Test: `backend/tests/test_review_service.py`
- Test: `backend/tests/test_class_service.py`
- Test: `backend/tests/test_guild_progression_service.py`

- [ ] **Step 1: Write failing tests for scoped invalidation behavior**

```python
@pytest.mark.asyncio
async def test_invalidate_cache_scope_deletes_only_matching_user_keys():
    redis = AsyncMock()
    redis.scan_iter.return_value = _aiter([
        "qw:cache:user_rating:user:user_1:abc",
        "qw:cache:user_rating:user:user_2:def",
    ])

    with patch("app.core.cache.get_redis_client", new=AsyncMock(return_value=redis)):
        deleted = await invalidate_cache_scope("user_rating", "user", "user_1")

    assert deleted == 1
    redis.delete.assert_awaited_once_with("qw:cache:user_rating:user:user_1:abc")
```

- [ ] **Step 2: Run targeted tests to confirm the current implementation cannot scope-delete**

Run: `cd C:/QuestionWork/backend; .venv/Scripts/python.exe -m pytest tests/test_review_service.py tests/test_class_service.py tests/test_guild_progression_service.py -q --tb=short`

Expected: FAIL because the current cache key format does not preserve a stable semantic scope, and invalidation is prefix-wide only.

- [ ] **Step 3: Add cache key scope support in the shared cache helper**

```python
def _build_key(prefix: str, args: tuple, kwargs: dict, scope: str | None = None) -> str:
    ...
    if scope:
        return f"{_CACHE_KEY_NS}{prefix}:{scope}:{digest}"
    return f"{_CACHE_KEY_NS}{prefix}:{digest}"


def redis_cache(ttl_seconds: int = 300, key_prefix: str = "default", scope_builder: Callable | None = None) -> Callable:
    ...
    scope = scope_builder(*args, **kwargs) if scope_builder else None
    key = _build_key(key_prefix, args, kwargs, scope)


async def invalidate_cache_scope(prefix: str, *scope_parts: str) -> int:
    scope = ":".join(str(part) for part in scope_parts if part)
    pattern = f"{_CACHE_KEY_NS}{prefix}:{scope}:*"
    ...
```

- [ ] **Step 4: Attach semantic scopes to the affected caches and stop global prefix invalidation**

```python
@redis_cache(ttl_seconds=120, key_prefix="user_rating", scope_builder=lambda conn, user_id: f"user:{user_id}")
async def get_user_rating(conn: asyncpg.Connection, user_id: str) -> dict:
    ...

await invalidate_cache_scope("user_rating", "user", reviewee_id)
await invalidate_cache_scope("class_info", "user", user.id)
await invalidate_cache_scope("guild_progress", "guild", guild_id)
await invalidate_cache_scope("guild_card", "guild", guild_id)
```

- [ ] **Step 5: Re-run the targeted backend tests**

Run: `cd C:/QuestionWork/backend; .venv/Scripts/python.exe -m pytest tests/test_review_service.py tests/test_class_service.py tests/test_guild_progression_service.py -q --tb=short`

Expected: PASS.

- [ ] **Step 6: Run a broader backend regression sweep for touched services**

Run: `cd C:/QuestionWork/backend; .venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py tests/test_phase2_classes.py -q --tb=short`

Expected: PASS.

## Phase 2: Backend Retention Safety

### Task 2: Stop Unbounded Growth of analytics_events

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/analytics_service.py`
- Modify: `backend/app/jobs/scheduler.py`
- Modify: `backend/tests/test_analytics.py`
- Optional docs: `docs/adr/2026-03-28-analytics-events-retention.md`

- [ ] **Step 1: Write a failing retention test for analytics pruning**

```python
@pytest.mark.asyncio
async def test_prune_old_events_deletes_rows_older_than_retention_window():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=17)

    deleted = await prune_old_events(conn, retention_days=90)

    assert deleted == 17
    query = conn.fetchval.await_args.args[0]
    assert "DELETE FROM analytics_events" in query
```

- [ ] **Step 2: Run the analytics test file and confirm the prune helper does not exist yet**

Run: `cd C:/QuestionWork/backend; .venv/Scripts/python.exe -m pytest tests/test_analytics.py -q --tb=short`

Expected: FAIL because pruning is not implemented.

- [ ] **Step 3: Add an explicit retention setting with a safe default**

```python
class Settings(BaseSettings):
    ...
    ANALYTICS_EVENTS_RETENTION_DAYS: int = 90
```

- [ ] **Step 4: Implement a small analytics pruning helper instead of jumping straight to partitioning**

```python
async def prune_old_events(conn: asyncpg.Connection, retention_days: int) -> int:
    return int(
        await conn.fetchval(
            """
            WITH deleted AS (
                DELETE FROM analytics_events
                WHERE created_at < NOW() - ($1::text || ' days')::interval
                RETURNING 1
            )
            SELECT COUNT(*)::INT FROM deleted
            """,
            retention_days,
        )
        or 0
    )
```

- [ ] **Step 5: Call the prune helper from the scheduler loop on leader ticks**

```python
await analytics_service.prune_old_events(
    conn,
    retention_days=settings.ANALYTICS_EVENTS_RETENTION_DAYS,
)
```

- [ ] **Step 6: Re-run analytics tests**

Run: `cd C:/QuestionWork/backend; .venv/Scripts/python.exe -m pytest tests/test_analytics.py -q --tb=short`

Expected: PASS.

- [ ] **Step 7: Smoke the scheduler path without running the full stack**

Run: `cd C:/QuestionWork/backend; .venv/Scripts/python.exe -m pytest tests/ -q --tb=short -k "analytics or scheduler"`

Expected: PASS for touched analytics and scheduler-adjacent tests.

## Phase 3: Frontend Runtime Cleanup

### Task 3: Make LazyMotion Actually Effective

**Files:**
- Create: `frontend/src/lib/motion.ts`
- Modify: `frontend/src/components/ui/ClientAppShell.tsx`
- Modify: high-traffic motion consumers under `frontend/src/app/**` and `frontend/src/components/**`

- [ ] **Step 1: Add one thin shared motion import surface**

```typescript
export {
  AnimatePresence,
  LazyMotion,
  domAnimation,
  m as motion,
  useReducedMotion,
} from "framer-motion";

export type { Variants, Transition } from "framer-motion";
```

- [ ] **Step 2: Replace direct `framer-motion` imports in application files with the shared module**

```typescript
- import { motion, AnimatePresence } from "framer-motion";
+ import { motion, AnimatePresence } from "@/lib/motion";
```

- [ ] **Step 3: Verify only the wrapper and the shell still touch the raw package directly**

Run: `cd C:/QuestionWork/frontend; rg 'from "framer-motion"' src`

Expected: only `src/lib/motion.ts` and any intentionally retained shell-level import remain.

- [ ] **Step 4: Run frontend static verification**

Run: `cd C:/QuestionWork/frontend; npm run lint`

Expected: PASS.

- [ ] **Step 5: Run the TypeScript compile check**

Run: `cd C:/QuestionWork/frontend; npx tsc --noEmit`

Expected: PASS.

### Task 4: Move Authenticated Heavy Pages to useSWRFetch

**Files:**
- Modify: `frontend/src/app/profile/page.tsx`
- Modify: `frontend/src/app/profile/class/page.tsx`
- Modify: `frontend/src/app/disputes/page.tsx`
- Modify if needed: `frontend/src/hooks/useSWRFetch.ts`

- [ ] **Step 1: Keep the redirect/auth logic, but move read loading into SWR-backed fetchers**

```typescript
const {
  data: profileData,
  isLoading,
  error,
  mutate,
} = useSWRFetch(["profile", user?.id], async () => {
  if (!user?.id) throw new Error("missing-user");
  const [profile, badges, artifacts] = await Promise.all([
    getUserProfile(user.id),
    getMyBadges(),
    getUserArtifacts().catch(() => null),
  ]);
  return { profile, badges, artifacts };
});
```

- [ ] **Step 2: Keep explicit loading, error, and empty states on each page after the hook swap**

```typescript
if (isLoading) return <LoadingState />;
if (error) return <ErrorState onRetry={() => void mutate()} />;
if (!data) return <EmptyState />;
```

- [ ] **Step 3: Use the same pattern for disputes and class dashboard reads**

```typescript
const { data, isLoading, error, mutate } = useSWRFetch(
  ["my-disputes"],
  () => api.listMyDisputes(100, 0),
);
```

- [ ] **Step 4: Run lint and TypeScript again after the hook migration**

Run: `cd C:/QuestionWork/frontend; npm run lint`

Expected: PASS.

- [ ] **Step 5: Run the typecheck again to catch stale state and nullability mistakes**

Run: `cd C:/QuestionWork/frontend; npx tsc --noEmit`

Expected: PASS.

- [ ] **Step 6: Smoke the affected routes in the running frontend**

Run: open `/profile`, `/profile/class`, and `/disputes` while authenticated.

Expected: initial loading state renders, retry path still works, and revisits use cached SWR data rather than re-building each page from scratch.

## Deferred Track

These were verified as real repo state, but they are better handled in a dedicated modernization plan after the above fixes land:
- FastAPI version lag in `backend/requirements.txt`.
- No Linux-targeted `uvloop` path despite `httptools` already being installed.

## Self-Review

- Spec coverage: every confirmed issue from the verification pass is mapped to a task.
- Placeholder scan: removed vague items and kept exact files and commands.
- Type consistency: cache scoping stays in the shared cache layer; frontend motion changes route through one import surface; SWR adoption reuses the existing hook instead of inventing a second data layer.

Plan complete and saved to `docs/superpowers/plans/2026-03-28-audit-verification-fixes.md`.

Sequential handoff:

- Send `Фаза 1` and I will implement only cache-integrity work.
- After validation, send `Фаза 2` and I will implement only analytics retention work.
- After validation, send `Фаза 3` and I will implement only frontend runtime cleanup.

Do not batch phases together unless you explicitly want one larger change set.