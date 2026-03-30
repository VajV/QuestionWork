# Performance Improvements Plan — QuestionWork

**Created**: 2026-03-28  
**Goal**: Eliminate 10 identified performance bottlenecks across backend (FastAPI/asyncpg) and frontend (Next.js 14) to improve page load speed, reduce server resource usage, and enable SEO for public pages.

---

## Architecture Context

| Layer | Stack | Key files |
|-------|-------|-----------|
| Backend | FastAPI + asyncpg + PostgreSQL 15 + Redis 7 | `backend/app/` |
| Frontend | Next.js 14.2.35 App Router + TS 5 + Tailwind 3.4.1 + Framer Motion 12.34.3 | `frontend/src/` |
| Infra | Docker Compose (postgres, redis, jaeger, otel-collector) | `docker-compose.dev.yml` |
| Migrations | Alembic (73 versions, latest `z4d5e6f7g8h9`) | `backend/alembic/versions/` |

---

## File Structure

```
backend/
  app/
    core/
      config.py               <- Task 4: pool defaults
      redis_client.py          <- Task 7: response cache helper
      cache.py                 <- Task 7: NEW — Redis cache decorator
    db/
      session.py               <- Task 4: remove SELECT 1 setup
    services/
      quest_service.py         <- Task 6: explicit columns (~40 SELECT *)
      admin_service.py         <- Task 6: explicit columns (8 SELECT *)
      dispute_service.py       <- Task 6: explicit columns (6 SELECT *)
      class_service.py         <- Task 6: explicit columns (4 SELECT *)
      event_service.py         <- Task 6: explicit columns (4 SELECT *)
      badge_service.py         <- Task 6: explicit columns (1 SELECT *)
      admin_runtime_service.py <- Task 6: explicit columns (4 SELECT *)
      guild_card_service.py    <- Task 6: explicit columns (2 SELECT *)
      matching_service.py      <- Task 6: explicit columns (1 SELECT *)
      template_service.py      <- Task 6: explicit columns (3 SELECT *)
  alembic/versions/
    NEW_add_performance_indexes.py <- Task 5: missing indexes

frontend/
  src/
    app/
      layout.tsx               <- Task 2: next/font integration
      globals.css              <- Task 2: remove @import fonts
      page.tsx                 <- Task 9: SSR candidate (landing)
      for-clients/page.tsx     <- already server component
    components/
      onboarding/
        OnboardingWizard.tsx   <- Task 3: next/image (2 img tags)
      home/
        HomeClientSection.tsx  <- Task 9: NEW — client island
    hooks/
      useSWRFetch.ts           <- Task 10: NEW — SWR wrapper hook
  next.config.mjs              <- Task 1, 3: analyzer + image domains
  package.json                 <- Task 1, 10: add analyzer + swr
```

---

## Phase 1 — Quick Wins (Low risk, immediate impact)

### Task 1: Install and configure bundle analyzer

**Why**: Unknown JS bundle composition. Framer Motion alone can add 60+ KB gzipped.

**Files**: `frontend/package.json`, `frontend/next.config.mjs`

- [ ] 1.1 Install:
  ```bash
  cd frontend && npm install --save-dev @next/bundle-analyzer
  ```

- [ ] 1.2 Edit `frontend/next.config.mjs` — wrap config:
  ```javascript
  import withBundleAnalyzer from "@next/bundle-analyzer";
  const analyzeBundles = withBundleAnalyzer({ enabled: process.env.ANALYZE === "true" });
  // ... existing nextConfig ...
  export default analyzeBundles(nextConfig);
  ```

- [ ] 1.3 Verify: `ANALYZE=true npm run build` opens `.next/analyze/`.
- [ ] 1.4 Rollback: `npm uninstall @next/bundle-analyzer`, revert `next.config.mjs`.

---

### Task 2: Migrate Google Fonts from CSS @import to next/font

**Why**: CSS `@import url(...)` is render-blocking. `next/font` self-hosts and adds `font-display: swap`.

**Current** (`frontend/src/app/globals.css` line 1):
```css
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Inter:wght@300;400;500;600;700;900&family=JetBrains+Mono:wght@400;500;700&display=swap');
```

**Files**: `globals.css`, `layout.tsx`, `next.config.mjs`, `tailwind.config.ts`

- [ ] 2.1 Edit `layout.tsx` — add next/font imports:
  ```typescript
  import { Inter, JetBrains_Mono } from "next/font/google";
  import localFont from "next/font/local";

  const inter = Inter({
    subsets: ["latin", "cyrillic"],
    weight: ["300", "400", "500", "600", "700", "900"],
    variable: "--font-inter", display: "swap",
  });
  const jetbrainsMono = JetBrains_Mono({
    subsets: ["latin", "cyrillic"],
    weight: ["400", "500", "700"],
    variable: "--font-jetbrains-mono", display: "swap",
  });
  const cinzel = localFont({
    src: "./fonts/Cinzel-VariableFont_wght.ttf",
    variable: "--font-cinzel", display: "swap", weight: "400 700",
  });
  ```
  Apply `className={...inter.variable} ${jetbrainsMono.variable} ${cinzel.variable}...}` on `<html>`.

- [ ] 2.2 Download Cinzel variable font to `frontend/src/app/fonts/`.
- [ ] 2.3 Remove the `@import` line from `globals.css`.
- [ ] 2.4 Update CSP in `next.config.mjs`: remove `fonts.googleapis.com`/`fonts.gstatic.com`.
- [ ] 2.5 Map CSS vars in `tailwind.config.ts`:
  ```typescript
  fontFamily: {
    sans: ["var(--font-inter)", "system-ui", "sans-serif"],
    display: ["var(--font-cinzel)", "serif"],
    mono: ["var(--font-jetbrains-mono)", "monospace"],
  },
  ```
- [ ] 2.6 Verify: `npm run build`; no `fonts.googleapis.com` network requests.
- [ ] 2.7 Rollback: Revert all 4 files, delete `fonts/`.

---

### Task 3: Replace raw img tags with next/image

**Why**: Raw `<img>` skips WebP/AVIF conversion, lazy loading, srcset.

**Locations** (2 in `OnboardingWizard.tsx`): line 410 (avatar), line 500 (badge icon).

- [ ] 3.1 Add `images.remotePatterns` to `next.config.mjs`:
  ```javascript
  images: { remotePatterns: [{ protocol: "http", hostname: "127.0.0.1", port: "8001", pathname: "/uploads/**" }] },
  ```
- [ ] 3.2 Replace avatar img (line ~410):
  ```tsx
  import Image from "next/image";
  <Image src={displayedAvatar} alt="Avatar preview" fill className="object-cover"
    sizes="96px" unoptimized={displayedAvatar.startsWith("data:")} />
  ```
- [ ] 3.3 Replace badge icon img (line ~500):
  ```tsx
  <Image src={earnedBadges[0].badge_icon} alt={earnedBadges[0].badge_name}
    width={64} height={64} onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
  ```
- [ ] 3.4 Ensure parent has `position: relative` for `fill`.
- [ ] 3.5 Verify: `npx tsc --noEmit` + `npm run build`.
- [ ] 3.6 Rollback: Revert `OnboardingWizard.tsx`, `next.config.mjs`.

---

### Task 4: Remove pool connection validation query

**Why**: `setup=_validate_connection` runs `SELECT 1` on **every** `pool.acquire()` (~0.5ms/req overhead).

**File**: `backend/app/db/session.py`

- [ ] 4.1 Remove `setup=_validate_connection` from `create_pool()`.
- [ ] 4.2 Remove the `_validate_connection` function.
- [ ] 4.3 Verify: all 1093 backend tests pass.
- [ ] 4.4 Rollback: Restore parameter and function.

---

## Phase 2 — Medium Effort (Moderate risk, high impact)

### Task 5: Add missing database indexes

**Why**: Tables `user_badges`, `background_jobs`, `guild_members`, `disputes` lack indexes on frequently-queried columns.

**Existing**: quests(status, client_id, assigned_to, ...), applications(quest_id, freelancer_id), transactions(user_id, quest_id), users(grade, role, skills GIN).

**Missing**: `user_badges(user_id)`, `background_jobs(status, scheduled_for)`, `guild_members(guild_id)`, `disputes(status)`.

- [ ] 5.1 Generate: `alembic revision -m "add_performance_indexes"`
- [ ] 5.2 Write migration with `CREATE INDEX CONCURRENTLY IF NOT EXISTS` in `autocommit_block()`:
  ```python
  def upgrade() -> None:
      with op.get_context().autocommit_block():
          op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_badges_user_id ON user_badges (user_id)")
      with op.get_context().autocommit_block():
          op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_background_jobs_status_scheduled ON background_jobs (status, scheduled_for)")
      with op.get_context().autocommit_block():
          op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_guild_members_guild_id ON guild_members (guild_id)")
      with op.get_context().autocommit_block():
          op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_disputes_status ON disputes (status)")

  def downgrade() -> None:
      op.execute("DROP INDEX IF EXISTS idx_disputes_status")
      op.execute("DROP INDEX IF EXISTS idx_guild_members_guild_id")
      op.execute("DROP INDEX IF EXISTS idx_background_jobs_status_scheduled")
      op.execute("DROP INDEX IF EXISTS idx_user_badges_user_id")
  ```
- [ ] 5.3 Apply: `alembic upgrade head`
- [ ] 5.4 Verify: `SELECT indexname FROM pg_indexes WHERE tablename IN (...)`
- [ ] 5.5 Rollback: `alembic downgrade -1`

---

### Task 6: Replace SELECT * with explicit column lists

**Why**: 81 `SELECT *` across 9 services pull heavy JSONB columns unnecessarily.

**Priority**: quest_service (~40), admin_service (8), dispute_service (6).

- [ ] 6.1 For each query in `quest_service.py`, identify used columns, replace `SELECT *` with explicit list. Keep `FOR UPDATE` clauses.
- [ ] 6.2 Same for `admin_service.py` (transactions, quests, applications, user_class_progress).
- [ ] 6.3 Same for `dispute_service.py` (disputes).
- [ ] 6.4 Verify: all backend tests pass.
- [ ] 6.5 Follow-up: remaining 6 services.
- [ ] 6.6 Rollback: `git checkout` per service file.

---

### Task 7: Add Redis API response cache decorator

**Why**: Redis runs but only for rate limiting/pubsub. Read endpoints re-query PG every time.

- [ ] 7.1 Create `backend/app/core/cache.py` with `redis_cache(ttl_seconds, key_prefix)` decorator:
  - Best-effort (falls through on Redis failure)
  - Skips `asyncpg.Connection` in key hash
  - `invalidate_cache(pattern)` helper
- [ ] 7.2 Apply to `badge_service.get_all_badges()` with TTL=300s.
- [ ] 7.3 Verify: tests pass, second `/badges/catalogue` call serves from cache.
- [ ] 7.4 Rollback: delete `cache.py`, revert `badge_service.py`.

---

### Task 8: Nginx static file config for production

**Why**: `/uploads` served via Python `StaticFiles` wastes async workers.

- [ ] 8.1 Create `nginx/default.conf` with `location /uploads/` serving files directly with `Cache-Control: public, immutable`.
- [ ] 8.2 Dev uses `StaticFiles` as-is (no code change).
- [ ] 8.3 Verify in production: uploads served with correct headers.
- [ ] 8.4 Rollback: remove `nginx/` directory.

---

## Phase 3 — Heavy Lifts (Higher risk, strategic impact)

### Task 9: Convert landing page to Server Component

**Why**: `page.tsx` is `"use client"` — all marketing content ships as client JS. Primary SEO page.

**20/39 pages are "use client"**. Priority: landing, marketplace, badges, users.

- [ ] 9.1 Extract interactive parts into `HomeClientSection.tsx` ("use client").
- [ ] 9.2 Refactor `page.tsx` to server component importing `ClientProofStrip`, `ClientTrustGrid`, `HomeClientSection`.
- [ ] 9.3 Add `export const metadata` for SEO.
- [ ] 9.4 Verify: build output shows landing as server-rendered. `view-source:` has meta tags.
- [ ] 9.5 Rollback: revert `page.tsx`, delete `HomeClientSection.tsx`.

---

### Task 10: Add SWR for client-side data fetching

**Why**: No caching layer — every navigation refetches. 0 SWR/react-query usage.

- [ ] 10.1 Install: `npm install swr`
- [ ] 10.2 Create `useSWRFetch.ts` hook wrapping `fetchApi`:
  ```typescript
  export function useSWRFetch<T>(path: string | null, requiresAuth = false, config?) {
    return useSWR<T, ApiError>(path,
      (url) => fetchApi<T>(url, { method: "GET" }, requiresAuth),
      { revalidateOnFocus: true, dedupingInterval: 5000, errorRetryCount: 2, ...config });
  }
  ```
- [ ] 10.3 Apply to badges page as PoC: replace `useEffect+useState` with `useSWRFetch`.
- [ ] 10.4 Verify: tsc passes, second navigation is instant.
- [ ] 10.5 Rollback: `npm uninstall swr`, delete hook, revert page.

---

## Execution Summary

| # | Task | Phase | Risk | Files |
|---|------|-------|------|-------|
| 1 | Bundle analyzer | 1 | Low | 2 |
| 2 | next/font migration | 1 | Low | 4 |
| 3 | next/image | 1 | Low | 2 |
| 4 | Remove pool SELECT 1 | 1 | Low | 1 |
| 5 | Missing DB indexes | 2 | Medium | 1 |
| 6 | SELECT * cleanup | 2 | Medium | 3-10 |
| 7 | Redis response cache | 2 | Medium | 2 |
| 8 | Nginx static files | 2 | Medium | 2 |
| 9 | Landing page SSR | 3 | Higher | 2-3 |
| 10 | SWR integration | 3 | Higher | 3+ |

## Self-Review Checklist

- [x] Every task specifies exact file paths
- [x] Code blocks are complete
- [x] Every task has verify and rollback steps
- [x] Follows codebase conventions
- [x] Phase order respects dependencies
- [x] No breaking changes
- [x] Alembic migration has upgrade() and downgrade()
- [x] Frontend changes maintain TypeScript strictness
- [x] Backend changes preserve test coverage
