# 90-Day Growth Roadmap Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert QuestionWork from a themed freelance marketplace into a trust-oriented, measurable, repeatable hiring system over the next 90 days.

**Architecture:** The quarter is sequenced around four compounding layers: instrumentation and trust foundations, client demand capture, posting and supply conversion, then retention and repeat loops. Each week ends with a demoable surface plus one measurable KPI change or new measurement capability.

**Tech Stack:** Next.js 14 App Router, TypeScript, React, Tailwind, Framer Motion, FastAPI, asyncpg, PostgreSQL, Redis, notification/email services

---

## Weekly Roadmap

### Week 1: KPI spine and event taxonomy
**Primary outcome:** the team can see the funnel, not guess it.

- [ ] Define the quarterly scorecard in [docs/superpowers/plans/PlansGapMap/04-retention-crm-and-analytics-implementation-plan.md](04-retention-crm-and-analytics-implementation-plan.md).
- [ ] Add event taxonomy for `landing_view`, `client_cta_click`, `register_started`, `register_completed`, `quest_create_started`, `quest_created`, `application_submitted`, `hire_completed`, `quest_confirmed`, `repeat_hire_started`.
- [ ] Choose one analytics sink for the quarter and wire the client/server event adapters.
- [ ] Add a zero-friction env-based analytics toggle for local/dev.
- [ ] Publish the first funnel dashboard and baseline numbers.

**Exit criteria:** baseline funnel exists and every later feature in the quarter can attach to the same event vocabulary.

### Week 2: Client trust baseline
**Primary outcome:** a new client immediately understands why the platform is safe enough to try.

- [ ] Rewrite the main landing narrative so client value is explicit, not implied by guild theme alone.
- [ ] Add a dedicated client-first surface and trust blocks: process, escrow, dispute handling, speed, vetting.
- [ ] Add proof components that can be reused on landing, quest posting, and profile surfaces.
- [ ] Expose existing market numbers only where they are real; mark placeholders for removal if synthetic.
- [ ] Add analytics to each trust block interaction and CTA.

**Exit criteria:** new client journey has a clear “why post here” answer before registration.

### Week 3: Client acquisition surfaces
**Primary outcome:** inbound demand can enter through use-case pages rather than a single generic homepage.

- [ ] Ship one hub page for hiring entry.
- [ ] Ship 3-5 SEO/indexable use-case pages by stack/urgency.
- [ ] Add lead capture before full registration where the user is not ready to post immediately.
- [ ] Add first outbound follow-up cadence for captured leads that did not start registration or quest posting.
- [ ] Add source/UTM attribution persistence.
- [ ] Add internal links from homepage, header, footer, and quest/talent surfaces.

**Exit criteria:** at least one client acquisition path bypasses the generic homepage-only route.

### Week 4: Guided quest posting v1
**Primary outcome:** first-time clients can publish a quest without inventing the process themselves.

- [ ] Rework quest creation into a guided flow with progressive disclosure.
- [ ] Add templates for common job types and recommended defaults.
- [ ] Add budget, grade, and deadline guidance with validation copy.
- [ ] Add saved draft support and “continue later” flow.
- [ ] Add quest creation funnel metrics and abandonment points.

**Exit criteria:** quest creation becomes an assisted workflow rather than a raw form.

### Week 5: Supply proof v1
**Primary outcome:** talent is legible and comparable.

- [ ] Expand public freelancer profiles with proof fields.
- [ ] Enrich marketplace rows with quality signals instead of mostly RPG identity.
- [ ] Add featured experts and featured guilds logic for curated discovery.
- [ ] Add guided freelancer credibility onboarding so a new account can become hireable quickly.
- [ ] Define transparent ranking factors and expose them selectively in UI copy.
- [ ] Instrument profile views, contact intent, shortlist actions, and hire starts.

**Exit criteria:** buyer can explain why one freelancer looks safer than another.

### Week 6: Comparison and shortlist tools
**Primary outcome:** clients can move from browsing to selecting.

- [ ] Add save/favorite talent.
- [ ] Add shortlist state on marketplace/profile surfaces.
- [ ] Add a comparison surface for 2-4 candidates.
- [ ] Add “invite to apply” or “return to shortlisted talent” hooks.
- [ ] Track shortlist-to-hire conversion.

**Exit criteria:** the platform supports a hiring workflow, not just passive discovery.

### Week 7: Demand-to-supply matching v1
**Primary outcome:** quest posting and talent discovery reinforce each other.

- [ ] Show recommended talent after quest creation.
- [ ] Show suggested templates during quest creation.
- [ ] Add relevant talent modules on quest detail pages.
- [ ] Add empty-state recovery flows when a category has low liquidity.
- [ ] Add internal notifications or emails for matching events.

**Exit criteria:** a posted quest immediately produces a next best action.

### Week 8: Lifecycle CRM foundation
**Primary outcome:** key drop-off states trigger follow-up, not silence.

- [ ] Lock the quarter CRM decision: first-party lifecycle + outbox on FastAPI/Postgres, no third-party CRM dependency this quarter.
- [ ] Add notification/email matrix for incomplete profile, incomplete quest, stale shortlist, unreviewed completion, and dormant client.
- [ ] Add background-safe scheduling path for non-urgent lifecycle messaging.
- [ ] Add notification preferences baseline.
- [ ] Add campaign identifiers to lifecycle events.
- [ ] Measure open/click/return for lifecycle messages where possible.

**Exit criteria:** the product can nudge users back into the funnel.

### Week 9: Repeat hire loop
**Primary outcome:** successful transaction generates another opportunity by default.

- [ ] Add “hire again”, “create similar quest”, and “reinvite previous freelancer” actions.
- [ ] Add post-completion summary card for clients.
- [ ] Add reactivation message cadence at 7/14/30 days after completion.
- [ ] Track repeat hire rate and time-to-second-quest.

**Exit criteria:** a completed quest opens the next cycle instead of closing the relationship.

### Week 10: Saved demand and alerts
**Primary outcome:** clients and freelancers have a reason to return even without a current active transaction.

- [ ] Add saved searches or saved filters for talent and/or quests.
- [ ] Add alerts/digests for new relevant matches.
- [ ] Add simple notification center filtering for growth-triggered events.
- [ ] Track save-to-return and alert-to-session metrics.

**Exit criteria:** return visits are supported by product memory.

### Week 11: Experiment cadence
**Primary outcome:** the team can improve conversion with evidence.

- [ ] Choose first experiment backlog: client CTA copy, quest posting order, profile proof layout, shortlist CTA.
- [ ] Add experiment flag mechanism if not already present.
- [ ] Publish weekly reporting ritual and owner table.
- [ ] Define stop/continue thresholds.

**Exit criteria:** roadmap transitions from project mode to operating cadence.

### Week 12: Hardening and synthesis
**Primary outcome:** the quarter’s new surfaces work together coherently.

- [ ] Tighten navigation links between landing, hiring, posting, marketplace, and profiles.
- [ ] Remove dead-end states and placeholder copy.
- [ ] Run end-to-end QA on the primary client journey and primary freelancer journey.
- [ ] Patch analytics blind spots discovered during rollout.

**Exit criteria:** the new growth layer behaves as one system.

### Week 13: Quarter close and next-quarter handoff
**Primary outcome:** the team knows what changed and what to do next.

- [ ] Compare new KPI baselines to week 1 baseline.
- [ ] Freeze a `Q2 growth learnings` document.
- [ ] Rank next-quarter work by observed impact, not intuition.
- [ ] Move remaining nice-to-have items to backlog.

**Exit criteria:** the roadmap ends with measured learning, not just shipped tickets.

---

## Phase Gates

## Chunk 1: Foundation Gate (Weeks 1-3)
- [ ] No launch to later phases unless funnel instrumentation, attribution, and client trust surfaces are live.

## Chunk 2: Conversion Gate (Weeks 4-7)
- [ ] No retention work takes priority over guided posting, profile proof, and shortlist mechanics.

## Chunk 3: Retention Gate (Weeks 8-10)
- [ ] No advanced gamification work enters scope before repeat-hire loops and lifecycle CRM basics are shipped.

## Chunk 4: Operating Gate (Weeks 11-13)
- [ ] End the quarter with experiment cadence, KPI review, and backlog reprioritization.

---

## Non-Negotiables
- [ ] Do not cut analytics instrumentation.
- [ ] Do not cut buyer trust improvements.
- [ ] Do not cut guided quest posting.
- [ ] Do not treat synthetic showcase data as proof in production messaging.
- [ ] Do not expand guild/social depth until transaction loops improve.

## Suggested Execution Order
1. Execute [02-demand-and-trust-implementation-plan.md](02-demand-and-trust-implementation-plan.md)
2. Execute [03-posting-supply-and-conversion-implementation-plan.md](03-posting-supply-and-conversion-implementation-plan.md)
3. Execute [04-retention-crm-and-analytics-implementation-plan.md](04-retention-crm-and-analytics-implementation-plan.md)
4. Run [99-coverage-check.md](99-coverage-check.md)
