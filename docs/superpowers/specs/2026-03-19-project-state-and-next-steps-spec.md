# QuestionWork — Project State & Next-Steps Spec

**Date:** 2026-03-19  
**Status:** Approved for planning  
**Scope:** Full project audit → gap analysis → feature wishlist  
**Author:** Brainstorming pass (Copilot + /brainstorming skill)

---

## 1. Purpose

This spec summarises what is **already shipped**, what is **half-done**, and what **doesn't exist yet** in the QuestionWork codebase as of March 2026.  
It is the input for the matching implementation plan (`2026-03-19-post-mvp-roadmap-plan.md`).

---

## 2. Project Status Overview

QuestionWork is an IT freelance marketplace with RPG gamification built on:
- **Backend:** FastAPI 0.100+ / Python 3.12 / asyncpg / PostgreSQL / Redis / ARQ
- **Frontend:** Next.js 14 App Router / TypeScript / Tailwind CSS / Framer Motion

Overall readiness: **~75% production-ready**.  
Core business flows (register → create quest → apply → complete → pay out) are end-to-end functional. The remaining gaps are a mix of security fixes, incomplete subsystems, and post-MVP features.

---

## 3. What IS Implemented

### 3.1 Core Business Flows — ✅ Complete

| Domain | Status | Notes |
|--------|--------|-------|
| User registration / login / logout | ✅ | JWT + bcrypt + refresh rotation |
| User profiles (bio, skills, avatar) | ✅ | Avatar upload, onboarding tracking |
| Quest lifecycle (draft → confirmed) | ✅ | Full 9-state machine |
| Freelancer applications & assignment | ✅ | Includes recommended-freelancers |
| Escrow wallet (hold → release) | ✅ | Multi-currency, platform fee split |
| Withdrawals (request → admin approve) | ✅ | Idempotency keys, auto-approval trust-layer job |
| Transaction history + PDF receipts | ✅ | Monthly statements too |
| Notifications (in-app) | ✅ | Cursor pagination, preferences, read-all |
| Reviews & ratings | ✅ | AVG rating, XP bonus, email notify |
| Disputes (open → respond → resolve) | ✅ | Escrow settlement on resolution |
| Quest messaging | ✅ | In-quest chat, dialog list, unread counters |
| Admin dashboard | ✅ | Users, quests, wallet, withdrawals, broadcast, audit logs |
| Admin TOTP + IP allowlist | ✅ | 2FA setup, validation, IP enforcement |
| Badge system | ✅ | Catalogue, auto-earn, user badges |
| RPG grades (Novice→Senior) | ✅ | XP tracking, level-up, stat points |
| Character classes — berserk | ✅ | Perks, abilities, perk unlock |
| Seasonal events | ✅ | CRUD, leaderboard, join, score, finalization job |
| Guilds (basic) | ✅ | Create, join/leave, member list, treasury |
| Quest templates | ✅ | CRUD + create-from-template |
| Saved searches | ✅ | Create, list, delete |
| Shortlists | ✅ | Add/remove freelancers |
| Smart matching | ✅ | Skill-based quest ↔ freelancer recommendations |
| Trust score | ✅ | Aggregate rating/completion, cached in users table |
| Analytics event tracking | ✅ | Store events, query metrics by date range |
| Lead capture | ✅ | name/email/phone/company/message stored in DB |
| Background jobs (ARQ) | ✅ | Worker + scheduler + command_queue + job_queue |
| Admin runtime observability | ✅ | Commands, jobs, operations feed, endpoint health |
| Invoice / PDF receipts (basic) | ✅ | Per-transaction receipt; monthly statement |

### 3.2 Frontend Pages — ✅ Routed

`/`, `/auth/login`, `/auth/register`, `/onboarding`, `/profile`, `/profile/setup`, `/profile/quests`, `/quests`, `/quests/[id]`, `/quests/create`, `/quests/templates`, `/users`, `/users/[id]`, `/notifications`, `/messages`, `/badges`, `/disputes`, `/disputes/[id]`, `/events`, `/events/[id]`, `/for-clients`, `/admin/*`, `/hire`, `/marketplace`

---

## 4. What is Half-Done (⚠️ Gaps)

### 4.1 Security — must fix before production

| ID | Issue | Risk |
|----|-------|------|
| H-01 | TOTP setup skips IP allowlist check | Admin account takeover |
| H-02 | `QuestUpdate.budget` allows `ge=0` | Economy abuse |
| H-03 | Platform fee computed at payout, not at creation | Unpredictable income for freelancer |
| H-04 | `custom_xp` in QuestCreate is unbounded | XP inflation |
| H-05 | 5 of 6 character classes are empty stubs | Bad UX + hollow class select |
| H-06 | Class confirm skips trial-expiry check | User locks class after trial window |
| H-07 | Delivery URL accepts HTTP (should be HTTPS only) | XSS / malware risk |

### 4.2 Code Quality — medium priority

| ID | Issue |
|----|-------|
| M-01 | Frontend: missing Error Boundaries on complex pages |
| M-02 | Frontend API client: no retry on 429/503 |
| M-03 | Frontend: WalletPanel unmount race condition |
| M-04 | Backend admin docs: unclear role + IP requirements |

### 4.3 Infrastructure — must fix before production

- Secret management: hardcoded defaults in docker-compose
- CI/CD targets Python 3.11 instead of 3.12
- `COOKIE_SECURE=False` by default
- Admin IP allowlist empty by default (allows all in prod)

### 4.4 Incomplete Subsystems

| Subsystem | What Exists | What's Missing |
|-----------|------------|---------------|
| **Character classes** | berserk fully defined; 5 stubs (rogue, alchemist, paladin, archmage, oracle) | Perk trees, ability definitions, stat modifiers for 5 classes |
| **Ability executor** | Ability activation endpoint works | Runtime effect of abilities — nothing happens when activated |
| **Guild leveling** | Tables exist (guild_seasons, guild_seasonal_rewards) | Season-end scoring, rank progression, reward distribution logic |
| **Email pipeline** | `email_outbox` table + async send job | SMTP config, template engine, transactional triggers not wired |
| **Invoice workflow** | Per-transaction PDF receipt | Formal invoice with client/freelancer details, VAT, invoice number sequence |
| **WebSocket / real-time** | Not started | Live chat, live notifications, presence indicators |
| **Dispute arbitration UI** | Backend resolve endpoint exists | Full arbitration panel in frontend admin |
| **Onboarding wizard** | Basic step tracking | Advanced multi-step wizard with class selection and perk intro |

---

## 5. What Does NOT Exist Yet (Post-MVP Ideas)

All items below are explicitly requested in `docs/ideas/` but none are MVP-blocking.

| # | Feature | Impact | Effort |
|---|---------|--------|--------|
| 1 | **WebSocket real-time messaging** | High — live chat UX | L |
| 2 | **Full invoice workflow** | Medium — billing compliance | M |
| 3 | **5 remaining character classes** | High — RPG core promise | XL |
| 4 | **Ability runtime effects** | Medium — class value prop | M |
| 5 | **Full email pipeline (SMTP + templates)** | High — user retention | M |
| 6 | **Advanced guild system** (season, rewards) | Medium — social/retention | L |
| 7 | **Advanced onboarding wizard** | Medium — activation rate | S |
| 8 | **Dispute arbitration frontend panel** | Medium — trust/safety | M |
| 9 | **Frontend real-time notifications** (SSE or WS) | High — engagement | M |
| 10 | **Referral system (full)** | Medium — growth | M |
| 11 | **Marketing pages polish** | Low — conversion | S |
| 12 | **Mobile-responsive audit** | Medium — reach | M |

---

## 6. Feature Ideas Worth Brainstorming (New Additions)

These are NOT in any existing plan documents — identified during this audit:

### 6.1 Quest Bidding / Counter-offers
Currently freelancers apply with a simple message. Adding budget counter-offer in the application (freelancer proposes own rate) would better match real marketplace behaviour.

### 6.2 Skill Verification Badges
Auto-award a "Verified Python Developer" badge when a user completes 3+ Python-tagged quests with ≥4.5 avg rating. Makes shortlisting more trustworthy.

### 6.3 Repeat Client Bonus
Small XP / perk-point bonus when a freelancer completes a 2nd+ quest with the same client. Encourages long-term relationships.

### 6.4 Quest Milestones (Staged Payments)
Split a quest budget into multiple milestones. Client releases escrow per milestone. Common in real platforms (Upwork, Freelancer.com).

### 6.5 Portfolio Projects
Separate from quests: freelancer can add portfolio items (title, description, URL, skills, thumbnail). Visible on public profile.

### 6.6 Client Reputation / Rating
Currently clients are not rated. Add a client rating (freelancer rates client after quest confirms). Visible on client profile and in quest listings.

### 6.7 Notification Digest Email
Daily/weekly email summarising unread notifications, new matching quests. Ties into the existing email_outbox + scheduler.

### 6.8 Admin Analytics Dashboard
Currently `/admin/stats` returns raw counts. A proper analytics page with charts (daily quests created, revenue, active users over time) using stored analytics events.

### 6.9 Public API / Webhooks
Clients who want to integrate their own tools (Jira, Notion, Slack) could call a public API with an API key or receive webhook POSTs on quest status changes.

### 6.10 Two-sided Search (Client finds freelancers, Freelancer finds clients)
Talent marketplace exists but the `/marketplace/talent` endpoint isn't linked from the main quest flow. Make it a first-class search experience.

---

## 7. Constraints & Non-Goals

- This spec does NOT prescribe DB schema changes — those belong in migration files.
- WebSocket implementation is explicitly out of scope for the next plan phase (too large, separate spec needed).
- No breaking changes to existing API contract without versioning.
- Admin TOTP and IP allowlist fixes must land before any other security work.

---

## 8. Recommended Sequencing

```
Phase 0 (now):    Security fixes H-01 → H-07  +  infra hardening
Phase 1 (week 1): M-01 → M-04 code quality + email pipeline
Phase 2 (week 2): Complete 5 character classes + ability executor
Phase 3 (week 3): Guild leveling season logic + advanced onboarding
Phase 4 (week 4): Quest milestones OR client ratings (pick one for MVP+1)
Phase 5+:         WebSocket, portfolio, public API, full invoice
```

---

*See matching plan: `docs/superpowers/plans/2026-03-19-post-mvp-roadmap-plan.md`*
