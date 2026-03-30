# Header Navigation Simplification Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce header overload by removing low-frequency duplicate destinations from the top navigation, keeping achievements inside the hero dossier/profile flow, removing participants from the header, and moving the notifications page entry into the bell dropdown header.

**Architecture:** The change is an information-architecture cleanup, not a feature rewrite. The header should only contain primary, high-frequency routes. Secondary destinations that already exist elsewhere should stay discoverable through the most natural parent surface: achievements in the hero dossier, notifications in the bell panel, and participants removed until a future event-oriented destination replaces it.

**Tech Stack:** Next.js App Router, React, TypeScript, existing Header and NotificationBell components, profile and directory pages.

---

## File Map

- Modify: `frontend/src/components/layout/Header.tsx`
  Responsibility: desktop/mobile global navigation and authenticated utility actions.
- Modify: `frontend/src/components/layout/NotificationBell.tsx`
  Responsibility: bell trigger, dropdown panel, quick actions, deep-link to full notifications page.
- Review only: `frontend/src/app/profile/page.tsx`
  Responsibility: hero dossier page that already contains the achievements block and link to all achievements.
- Review only: `frontend/src/app/badges/page.tsx`
  Responsibility: full achievements catalogue page.
- Review only: `frontend/src/app/users/page.tsx`
  Responsibility: participant directory page that will remain routable but lose header prominence.
- Test: navigation smoke via header interactions in desktop and mobile layouts.

---

## Product Decision

### What moves where

1. `Достижения` should be removed from the header.
   Reason: it is already represented inside the hero dossier in `frontend/src/app/profile/page.tsx` with a dedicated block and a `Все достижения →` CTA. Keeping it in the header duplicates a secondary destination and makes the header feel bloated.

2. `Участники` should be removed from the header.
   Reason: it is not a top-priority user journey compared to quests, guild/marketplace, dialogs, notifications, or contract creation. It also overlaps conceptually with guild discovery and can later be replaced by events or another stronger top-level destination.

3. `Уведомления` should be removed from the header nav and retained only through the bell dropdown.
   Reason: there is already a stronger affordance for notifications: the bell icon with unread count. The text nav item duplicates that path and visually overloads the header.

4. The bell dropdown header label `Уведомления` should become the primary deep-link to `/notifications`.
   Reason: this preserves discoverability while consolidating the notification entry into the existing interaction model.

### Resulting top-level header logic

- Keep: `Для заказчиков`
- Keep: `Доска заданий`
- Keep: `Гильдия`
- Keep when authenticated: `Диалоги`
- Keep utility actions: `+ Создать контракт`, `Админ`, bell icon, profile entry
- Remove: `Достижения`, `Участники`, `Уведомления`

This leaves the header focused on active workflow routes instead of archive/catalog routes.

---

## Chunk 1: Simplify Header IA

### Task 1: Remove duplicate secondary routes from global header

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`
- Review: `frontend/src/app/profile/page.tsx`
- Review: `frontend/src/app/users/page.tsx`
- Review: `frontend/src/app/badges/page.tsx`

- [ ] **Step 1: Confirm final nav inventory before editing**

Target desktop/mobile nav array should be:

```ts
[
  { href: "/for-clients", label: "Для заказчиков" },
  { href: "/quests", label: "Доска заданий" },
  { href: "/marketplace", label: "Гильдия" },
  ...(isAuthenticated ? [{ href: "/messages", label: "Диалоги" }] : []),
]
```

Expected outcome: no `Достижения`, no `Участники`, no `Уведомления` inside `navItems`.

- [ ] **Step 2: Remove the three links from the desktop header**

Implementation note:
- Change only the `navItems` construction.
- Do not alter contract creation, admin, bell, or profile controls.

Expected outcome:
- Desktop header becomes visually shorter.
- The authenticated utility cluster remains on the right.

- [ ] **Step 3: Remove the same three links from the mobile menu**

Implementation note:
- Because mobile nav is generated from the same `navItems`, verify the mobile drawer also loses those entries.

Expected outcome:
- Mobile menu mirrors the simplified desktop IA.

- [ ] **Step 4: Review profile achievements discoverability**

Review in `frontend/src/app/profile/page.tsx`:
- There is already a titled achievements block.
- There is already a `Все достижения →` link.

Decision:
- No extra header replacement is needed.
- If the block feels too far down the page later, promote it within the profile layout rather than restoring a header tab.

- [ ] **Step 5: Review participants fallback discoverability**

Review in `frontend/src/app/users/page.tsx`:
- Route stays alive.
- No immediate need for new entry point.

Decision:
- Keep `/users` routable but de-emphasized.
- Reintroduce top-level visibility only when it gains a stronger use case or becomes the future events destination.

- [ ] **Step 6: Smoke-test desktop and mobile header readability**

Manual checklist:
- Desktop header no longer wraps or feels visually overloaded.
- Mobile menu is shorter and easier to scan.
- No broken active-state underline logic.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout/Header.tsx
git commit -m "refactor: simplify header navigation"
```

---

## Chunk 2: Collapse Notifications Entry Into Bell Dropdown

### Task 2: Make bell dropdown header label the page entry point

**Files:**
- Modify: `frontend/src/components/layout/NotificationBell.tsx`
- Review: `frontend/src/app/notifications/page.tsx`

- [ ] **Step 1: Decide the new notification dropdown hierarchy**

Target hierarchy:
- Bell icon opens dropdown.
- Dropdown header row contains:
  - clickable title `Уведомления`
  - secondary action `Прочитать все` when unread items exist
- Bottom `Открыть все уведомления →` CTA should be removed or demoted if the title already performs the same navigation.

Expected outcome: one clear deep-link instead of two competing CTAs.

- [ ] **Step 2: Turn the dropdown title into a link to `/notifications`**

Implementation note:
- Replace the static header title with a `Link` to `/notifications`.
- Clicking it should close the panel the same way the bottom CTA currently does.

Desired interaction copy:
- `Уведомления`
- Optionally add subtle affordance styling so it reads as clickable, not just as a label.

- [ ] **Step 3: Remove redundant bottom CTA if it becomes unnecessary**

Decision rule:
- If header title is now the page-entry action, the bottom `Открыть все уведомления →` is redundant and should be removed.
- Keep the bottom area only if it serves another distinct quick action later.

Expected outcome: less clutter inside the dropdown.

- [ ] **Step 4: Preserve in-panel quick-use behavior**

Must remain unchanged:
- Recent notifications list
- Mark-as-read on open
- `Прочитать все`
- Error state with retry

This is a relocation of the deep-link, not a redesign of notification behavior.

- [ ] **Step 5: Smoke-test notification UX**

Manual checklist:
- Bell still opens reliably.
- Header label navigates to `/notifications`.
- `Прочитать все` still works independently.
- Dropdown no longer contains duplicated page-entry actions.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/NotificationBell.tsx
git commit -m "refactor: move notifications page entry into bell dropdown"
```

---

## Chunk 3: Validate IA After Cleanup

### Task 3: Verify the new navigation model is coherent

**Files:**
- Review: `frontend/src/components/layout/Header.tsx`
- Review: `frontend/src/components/layout/NotificationBell.tsx`
- Review: `frontend/src/app/profile/page.tsx`
- Review: `frontend/src/app/notifications/page.tsx`

- [ ] **Step 1: Validate destination ownership**

Ownership after change:
- Achievements belong to hero dossier/profile and the standalone badges page.
- Notifications belong to the bell system and the standalone notifications page.
- Participants remain a secondary directory route, not a primary nav destination.

- [ ] **Step 2: Validate discoverability tradeoffs**

Acceptable tradeoff:
- Slightly lower casual discoverability for `Achievements` and `Participants`

Benefit:
- Much higher clarity for primary actions in the header.

If users later miss achievements:
- strengthen the profile CTA or add a profile subnav tab
- do not re-bloat the global header

If users later need participants again:
- reintroduce it only with a stronger scoped concept, likely `Events` or a guild/community discovery surface

- [ ] **Step 3: Validate future extensibility**

The freed header space is reserved for:
- future events destination
- stronger guild/community feature
- operational states without wrapping the nav

- [ ] **Step 4: Final QA pass**

Run through:
- unauthenticated desktop header
- authenticated desktop header
- admin desktop header
- mobile menu
- bell dropdown with unread notifications
- bell dropdown with zero notifications

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/Header.tsx frontend/src/components/layout/NotificationBell.tsx
git commit -m "chore: validate streamlined navigation model"
```

---

## Recommended UX Call

If you want the sharpest version of this change, use this exact policy:

1. Remove `Достижения` from header entirely.
2. Remove `Участники` from header entirely.
3. Remove `Уведомления` from header entirely.
4. Keep achievements only in the hero dossier/profile plus `/badges` page.
5. Keep notifications entry only inside bell dropdown header.
6. Leave `/users` alive but not promoted.
7. Reserve the freed header slot for future `Ивенты` instead of another directory-style page.

This is the cleanest IA and matches your stated preference.

---

Plan complete and saved to `docs/superpowers/plans/2026-03-15-header-navigation-simplification.md`. Ready to execute?