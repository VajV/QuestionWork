# Frontend Feature Gaps Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three missing frontend features that already have backend endpoints: quest template editing, badge catalogue page, public user directory.

**Architecture:** Each feature adds minimal new code — API wrappers (where missing) + new pages/components following existing patterns from marketplace and profile pages. All data comes from existing backend endpoints with no backend changes needed.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, Framer Motion, Lucide icons, existing `fetchApi<T>()` client from `src/lib/api.ts`.

---

## Chunk 1: Quest Template Editing

### Task 1.1: Add API wrappers for getTemplate and updateTemplate

**Files:**
- Modify: `frontend/src/lib/api.ts` (after line ~1956, between `deleteTemplate` and `createQuestFromTemplate`)

- [ ] **Step 1: Add `getTemplate()` wrapper**

Insert after the `deleteTemplate` function (line ~1956):

```typescript
export async function getTemplate(
  templateId: string,
): Promise<QuestTemplate> {
  const response = await fetchApi<QuestTemplateRaw>(
    `/templates/${templateId}`,
    undefined,
    true,
  );
  return normalizeQuestTemplate(response);
}
```

- [ ] **Step 2: Add `UpdateTemplatePayload` interface and `updateTemplate()` wrapper**

Insert right after `getTemplate`:

```typescript
export interface UpdateTemplatePayload {
  name?: string;
  title?: string;
  description?: string;
  required_grade?: string;
  skills?: string[];
  budget?: number;
  currency?: string;
  is_urgent?: boolean;
  required_portfolio?: boolean;
}

export async function updateTemplate(
  templateId: string,
  payload: UpdateTemplatePayload,
): Promise<QuestTemplate> {
  const response = await fetchApi<QuestTemplateRaw>(
    `/templates/${templateId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    true,
  );
  return normalizeQuestTemplate(response);
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

### Task 1.2: Add edit flow to templates page

**Files:**
- Modify: `frontend/src/app/quests/templates/page.tsx`

The templates page currently has: create form, template list with delete + use-template buttons.
We need to add:
1. An "edit" button on each template card
2. When clicked, populate the create form with that template's data and switch to "edit mode"
3. A save button that calls `updateTemplate()` instead of `createTemplate()`

- [ ] **Step 1: Add imports for new API functions**

Add `getTemplate` and `updateTemplate` to the import from `@/lib/api` alongside existing imports. Also add `UpdateTemplatePayload` type.
Add the `Pencil` icon from `lucide-react` alongside existing icons.

- [ ] **Step 2: Add editing state variables**

Add state to track which template is being edited:

```typescript
const [editingId, setEditingId] = useState<string | null>(null);
```

- [ ] **Step 3: Create `handleEdit` function**

Load the template data into the form and set editingId:

```typescript
const handleEdit = useCallback((template: QuestTemplate) => {
  setForm({
    name: template.name,
    title: template.title,
    description: template.description || "",
    required_grade: template.required_grade,
    skills: template.skills.join(", "),
    budget: template.budget > 0 ? String(template.budget) : "",
    currency: template.currency || "RUB",
    is_urgent: template.is_urgent,
    required_portfolio: template.required_portfolio,
  });
  setEditingId(template.id);
  window.scrollTo({ top: 0, behavior: "smooth" });
}, []);
```

- [ ] **Step 4: Create `handleUpdate` function**

Send only changed fields to the backend:

```typescript
const handleUpdate = useCallback(async () => {
  if (!editingId) return;
  setLoading(true);
  setError(null);
  setSuccess(null);
  try {
    const payload: UpdateTemplatePayload = {
      name: form.name || undefined,
      title: form.title || undefined,
      description: form.description || undefined,
      required_grade: form.required_grade || undefined,
      skills: form.skills ? form.skills.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
      budget: form.budget ? parseFloat(form.budget) : undefined,
      currency: form.currency || undefined,
      is_urgent: form.is_urgent,
      required_portfolio: form.required_portfolio,
    };
    await updateTemplate(editingId, payload);
    setSuccess("Шаблон обновлён!");
    setEditingId(null);
    setForm({
      name: "",
      title: "",
      description: "",
      required_grade: "novice",
      skills: "",
      budget: "",
      currency: "RUB",
      is_urgent: false,
      required_portfolio: false,
    });
    await load();
    setTimeout(() => setSuccess(null), 3000);
  } catch (err) {
    setError((err as { detail?: string }).detail || "Не удалось обновить шаблон");
  } finally {
    setLoading(false);
  }
}, [editingId, form, load]);
```

- [ ] **Step 5: Add `handleCancelEdit` function**

```typescript
const handleCancelEdit = useCallback(() => {
  setEditingId(null);
  setForm({
    name: "",
    title: "",
    description: "",
    required_grade: "novice",
    skills: "",
    budget: "",
    currency: "RUB",
    is_urgent: false,
    required_portfolio: false,
  });
}, []);
```

- [ ] **Step 6: Update form heading and submit button**

Change the form section heading from static "Новый шаблон" to conditional:
- When `editingId` is set: "Редактирование шаблона" + cancel button
- When `editingId` is null: "Новый шаблон"

Change the submit button:
- When `editingId` is set: text "Сохранить", onClick calls `handleUpdate`
- When `editingId` is null: text "Создать шаблон", onClick calls `handleCreate` (existing)

- [ ] **Step 7: Add edit button to template cards**

In the template card actions area (next to delete and use-template buttons), add an edit button with `Pencil` icon:

```tsx
<button
  onClick={() => handleEdit(tpl)}
  className="p-2 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 transition-colors"
  title="Редактировать"
>
  <Pencil size={16} />
</button>
```

- [ ] **Step 8: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

---

## Chunk 2: Badge Catalogue Page

### Task 2.1: Create badge catalogue page

**Files:**
- Create: `frontend/src/app/badges/page.tsx`

This page shows all available badges from the platform catalogue (public endpoint `/badges/catalogue`). If the user is authenticated, it also loads their earned badges and highlights which ones they've already earned.

- [ ] **Step 1: Create the badge catalogue page**

Create `frontend/src/app/badges/page.tsx`:

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import { getBadgeCatalogue, getMyBadges } from "@/lib/api";
import type { Badge, UserBadgeEarned } from "@/lib/api";
import { Award, Lock, CheckCircle } from "lucide-react";

export default function BadgeCataloguePage() {
  const { isAuthenticated } = useAuth();
  const [badges, setBadges] = useState<Badge[]>([]);
  const [earned, setEarned] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [catalogue, myBadges] = await Promise.all([
        getBadgeCatalogue(),
        isAuthenticated ? getMyBadges() : Promise.resolve({ badges: [] as UserBadgeEarned[] }),
      ]);
      setBadges(catalogue.badges);
      setEarned(new Set(myBadges.badges.map((b) => b.badge_id)));
    } catch {
      setError("Не удалось загрузить каталог достижений.");
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-3xl font-cinzel text-amber-400 mb-2 flex items-center gap-3">
            <Award size={32} /> Каталог достижений
          </h1>
          <p className="text-gray-400 mb-8">
            Все доступные достижения на платформе. Выполняйте квесты и прокачивайтесь, чтобы открывать новые!
          </p>

          {loading && (
            <div className="text-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500 mx-auto mb-4" />
              <p className="text-gray-500">Загрузка каталога...</p>
            </div>
          )}

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 mb-6">
              {error}
            </div>
          )}

          {!loading && !error && badges.length === 0 && (
            <div className="text-center py-16">
              <Award size={48} className="mx-auto mb-4 text-gray-600" />
              <p className="text-gray-500">Каталог пока пуст.</p>
            </div>
          )}

          {!loading && !error && badges.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {badges.map((badge) => {
                const isEarned = earned.has(badge.id);
                return (
                  <motion.div
                    key={badge.id}
                    whileHover={{ scale: 1.05 }}
                    className={`relative flex flex-col items-center gap-3 rounded-xl border p-5 shadow-lg transition-all duration-300 cursor-default ${
                      isEarned
                        ? "border-purple-500/60 bg-purple-950/20 shadow-[0_0_15px_rgba(139,92,246,0.2)]"
                        : "border-gray-700/50 bg-gray-900/80"
                    }`}
                  >
                    {isEarned && (
                      <div className="absolute top-2 right-2">
                        <CheckCircle size={16} className="text-green-400" />
                      </div>
                    )}
                    {!isEarned && (
                      <div className="absolute top-2 right-2">
                        <Lock size={14} className="text-gray-600" />
                      </div>
                    )}
                    <span
                      className={`text-4xl drop-shadow-md ${
                        isEarned ? "drop-shadow-[0_0_8px_rgba(168,85,247,0.8)]" : "filter grayscale opacity-60"
                      }`}
                    >
                      {badge.icon}
                    </span>
                    <span className={`text-sm font-cinzel font-bold text-center leading-tight ${
                      isEarned ? "text-purple-200" : "text-gray-400"
                    }`}>
                      {badge.name}
                    </span>
                    <span className="text-[10px] text-center text-gray-500 line-clamp-2">
                      {badge.description}
                    </span>
                    <span className="text-[10px] font-mono text-gray-600 mt-auto border-t border-gray-800 w-full text-center pt-2">
                      {badge.criteria_type}: {badge.criteria_value}
                    </span>
                  </motion.div>
                );
              })}
            </div>
          )}
        </motion.div>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

### Task 2.2: Add badge catalogue link to navigation

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`

- [ ] **Step 1: Add "Достижения" link to navItems**

In the `navItems` useMemo array (line ~25-35), add the badge catalogue route:

```typescript
{ href: "/badges", label: "Достижения" },
```

Add it after the marketplace link so the order is: Доска заданий → Гильдия → Достижения → ...

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

### Task 2.3: Link badge catalogue from profile page

**Files:**
- Modify: `frontend/src/app/profile/page.tsx`

- [ ] **Step 1: Add "Все достижения" link next to badge section heading**

In the "Достижения" section heading area (around line ~490), add a small link to `/badges`:

```tsx
<Link href="/badges" className="text-xs text-amber-500/70 hover:text-amber-400 transition-colors ml-auto">
  Все достижения →
</Link>
```

Also add the `Link` import from `next/link` if not already present.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

---

## Chunk 3: Public User Directory

### Task 3.1: Create user directory page

**Files:**
- Create: `frontend/src/app/users/page.tsx`

This page lists all platform users with filtering by grade and sorting (by created_at, xp, level, username). Uses the existing `getAllUsers()` wrapper from api.ts.

- [ ] **Step 1: Create the user directory page**

Create `frontend/src/app/users/page.tsx`:

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import Button from "@/components/ui/Button";
import { getAllUsers } from "@/lib/api";
import type { PublicUserProfile, UserGrade } from "@/lib/api";
import { Users, Search, ChevronRight } from "lucide-react";

const PAGE_SIZE = 20;

const GRADE_OPTIONS: { value: UserGrade | "all"; label: string; color: string }[] = [
  { value: "all", label: "Все", color: "gray" },
  { value: "novice", label: "Novice", color: "gray" },
  { value: "junior", label: "Junior", color: "green" },
  { value: "middle", label: "Middle", color: "blue" },
  { value: "senior", label: "Senior", color: "purple" },
];

const SORT_OPTIONS: { value: "created_at" | "xp" | "level" | "username"; label: string }[] = [
  { value: "created_at", label: "Дата регистрации" },
  { value: "xp", label: "Опыт (XP)" },
  { value: "level", label: "Уровень" },
  { value: "username", label: "Имя" },
];

const GRADE_COLORS: Record<string, string> = {
  novice: "text-gray-400 border-gray-600",
  junior: "text-green-400 border-green-600",
  middle: "text-blue-400 border-blue-600",
  senior: "text-purple-400 border-purple-600",
};

export default function UserDirectoryPage() {
  const router = useRouter();
  const [users, setUsers] = useState<PublicUserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [grade, setGrade] = useState<UserGrade | "all">("all");
  const [sortBy, setSortBy] = useState<"created_at" | "xp" | "level" | "username">("xp");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getAllUsers(
        offset,
        PAGE_SIZE,
        grade === "all" ? undefined : grade,
        sortBy,
        sortOrder,
      );
      setUsers(result);
      setHasMore(result.length === PAGE_SIZE);
    } catch {
      setError("Не удалось загрузить список пользователей.");
    } finally {
      setLoading(false);
    }
  }, [offset, grade, sortBy, sortOrder]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setOffset(0);
  }, [grade, sortBy, sortOrder]);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-3xl font-cinzel text-amber-400 mb-2 flex items-center gap-3">
            <Users size={32} /> Участники платформы
          </h1>
          <p className="text-gray-400 mb-8">
            Найдите фрилансеров и заказчиков на платформе QuestionWork.
          </p>

          {/* Filters */}
          <div className="flex flex-wrap gap-4 mb-6">
            {/* Grade filter */}
            <div className="flex gap-1 rounded-lg bg-gray-900/50 p-1">
              {GRADE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setGrade(opt.value)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    grade === opt.value
                      ? "bg-amber-500/20 text-amber-400"
                      : "text-gray-400 hover:text-white hover:bg-gray-800"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            {/* Sort order */}
            <button
              onClick={() => setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))}
              className="px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-700 text-sm text-gray-300 hover:text-white transition-colors"
            >
              {sortOrder === "desc" ? "↓ По убыванию" : "↑ По возрастанию"}
            </button>
          </div>

          {/* Loading */}
          {loading && (
            <div className="text-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500 mx-auto mb-4" />
              <p className="text-gray-500">Загрузка...</p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 mb-6">
              {error}
            </div>
          )}

          {/* Empty */}
          {!loading && !error && users.length === 0 && (
            <div className="text-center py-16">
              <Users size={48} className="mx-auto mb-4 text-gray-600" />
              <p className="text-gray-500">Пользователи не найдены.</p>
            </div>
          )}

          {/* User list */}
          {!loading && !error && users.length > 0 && (
            <div className="space-y-3">
              {users.map((u) => (
                <motion.div
                  key={u.id}
                  whileHover={{ x: 4 }}
                  onClick={() => router.push(`/users/${u.id}`)}
                  className="flex items-center gap-4 rounded-xl border border-gray-800 bg-gray-900/60 p-4 cursor-pointer hover:border-amber-500/30 hover:bg-gray-900/80 transition-all"
                >
                  <LevelBadge level={u.level} size="sm" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-cinzel font-bold text-white truncate">
                        {u.username}
                      </span>
                      <span className={`text-[10px] uppercase tracking-wider font-mono border rounded px-1.5 py-0.5 ${GRADE_COLORS[u.grade] || "text-gray-400 border-gray-600"}`}>
                        {u.grade}
                      </span>
                      <span className="text-[10px] text-gray-500 capitalize">
                        {u.role === "freelancer" ? "фрилансер" : u.role === "client" ? "заказчик" : u.role}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                      <span>{u.xp} XP</span>
                      {u.character_class && <span className="capitalize">{u.character_class}</span>}
                      {u.skills.length > 0 && (
                        <span className="truncate max-w-[200px]">
                          {u.skills.slice(0, 3).join(", ")}
                          {u.skills.length > 3 && ` +${u.skills.length - 3}`}
                        </span>
                      )}
                    </div>
                  </div>
                  <ChevronRight size={18} className="text-gray-600" />
                </motion.div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {!loading && !error && (
            <div className="flex justify-center gap-3 mt-6">
              {offset > 0 && (
                <Button variant="secondary" onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}>
                  ← Назад
                </Button>
              )}
              {hasMore && users.length > 0 && (
                <Button variant="secondary" onClick={() => setOffset((prev) => prev + PAGE_SIZE)}>
                  Далее →
                </Button>
              )}
            </div>
          )}
        </motion.div>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

### Task 3.2: Add user directory link to navigation

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`

- [ ] **Step 1: Add "Участники" link to navItems**

In the `navItems` useMemo array, add the users directory route:

```typescript
{ href: "/users", label: "Участники" },
```

Add it after "Достижения" (from Chunk 2) so the order is: Доска заданий → Гильдия → Достижения → Участники → ...

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

---

## Chunk 4: Final Verification

### Task 4.1: Full build check

- [ ] **Step 1: Run full TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 2: Run production build**

Run: `cd frontend && npm run build`
Expected: all pages compile successfully, including new `/badges` and `/users` routes

- [ ] **Step 3: Verify new routes appear in build output**

Check that the build output includes:
- `/badges` — badge catalogue page
- `/users` — user directory page (distinct from `/users/[id]`)
- `/quests/templates` — should still compile with edit flow

### Task 4.2: Navigation verification

- [ ] **Step 1: Verify Header navItems includes new routes**

Grep the Header.tsx for "Достижения" and "Участники" to confirm they are in the nav.

---

## Summary

| Feature | API Wrappers | New Pages | Modified Files |
|---------|-------------|-----------|----------------|
| Template editing | `getTemplate`, `updateTemplate` + `UpdateTemplatePayload` in api.ts | — | api.ts, templates/page.tsx |
| Badge catalogue | Already exists (`getBadgeCatalogue`) | `/badges/page.tsx` | Header.tsx, profile/page.tsx |
| User directory | Already exists (`getAllUsers`) | `/users/page.tsx` | Header.tsx |

**Total new files:** 2 (badge catalogue page, user directory page)
**Total modified files:** 4 (api.ts, templates/page.tsx, Header.tsx, profile/page.tsx)
