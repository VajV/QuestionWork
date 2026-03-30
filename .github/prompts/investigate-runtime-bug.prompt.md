---
name: Investigate Runtime Bug
description: "Investigate a QuestionWork live-like runtime issue involving workers, scheduler, Redis, health endpoints, or runtime observability."
argument-hint: "Describe the runtime symptom"
agent: "agent"
---
Investigate the runtime issue in QuestionWork.

Requirements:
- Reproduce or isolate the failing runtime signal first
- Check health, readiness, worker, scheduler, and queue state
- Prefer targeted fixes over speculative rewrites
- Re-run the relevant verification command or script after changes
