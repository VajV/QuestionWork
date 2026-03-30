# Copilot Customizations

This repository uses native GitHub Copilot workspace customizations under `.github/` and a workspace MCP config in `.vscode/mcp.json`.

## What Exists

### Instructions
- `.github/instructions/backend.instructions.md`
- `.github/instructions/alembic.instructions.md`
- `.github/instructions/frontend.instructions.md`
- `.github/instructions/api-contract.instructions.md`
- `.github/instructions/tests.instructions.md`
- `.github/instructions/admin-security.instructions.md`

These files are applied automatically when the edited files match their `applyTo` rules or when the task context fits the instruction.

### Skills
- `backend-endpoint`: new or changed FastAPI endpoints, services, router registration, backend tests
- `alembic-safe-migration`: schema changes, indexes, backfills, downgrade-safe migrations
- `api-contract-sync`: backend Pydantic and frontend TypeScript/API contract alignment
- `quest-flow-regression`: quest lifecycle, escrow, payout, dispute, XP side effects
- `admin-security-audit`: admin/auth/TOTP/IP allowlist/security-sensitive review
- `live-runtime-debug`: worker, scheduler, Redis/ARQ, health and runtime triage

Skills live in `.github/skills/*/SKILL.md`. Use them when the task matches the area above.

### Agents
- `backend`: backend implementation and refactors
- `frontend`: Next.js and TypeScript UI work
- `migration`: Alembic migration work
- `security-review`: focused review of admin/auth/security-sensitive changes
- `release-readiness`: coordinator for pre-merge or pre-release verification

Agents live in `.github/agents/*.agent.md`.

### Prompts
- `create-backend-endpoint`
- `create-alembic-migration`
- `sync-api-contract`
- `run-regression-check`
- `investigate-runtime-bug`

Prompts live in `.github/prompts/*.prompt.md` and are meant to speed up repeatable tasks.

## Hooks

Hook policy is defined in `.github/hooks/policy.json`.

Current behavior:
- session start reminder that `.vscode/mcp.json` is the MCP source of truth
- pre-tool blocking for destructive git and generated-directory edits
- post-tool reminders when API contracts or high-risk business flows were touched

## MCP Servers

Active default MCP config is `.vscode/mcp.json`.

Verified on this Windows machine:
- `superpowers`
- `filesystem`
- `memory`
- `sequential-thinking`
- `playwright`

Windows note:
- npm CLI wrappers must use `npx.cmd`, not `npx`

Not enabled by default in the checked-in config:
- `postgres`: requires a real exported database URL in the VS Code environment
- `github`: requires a real exported GitHub personal access token for reliable authenticated use

If you want to enable them locally, use this pattern in `.vscode/mcp.json`:

```json
{
  "postgres": {
    "type": "stdio",
    "command": "npx.cmd",
    "args": [
      "-y",
      "@modelcontextprotocol/server-postgres",
      "${env:QUESTIONWORK_DATABASE_URL}"
    ]
  },
  "github": {
    "type": "stdio",
    "command": "npx.cmd",
    "args": [
      "-y",
      "@modelcontextprotocol/server-github"
    ],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_PERSONAL_ACCESS_TOKEN}"
    }
  }
}
```

## Recommended Use

For backend feature work:
- use the `backend-endpoint` skill
- run the `create-backend-endpoint` prompt if the task is mostly CRUD or endpoint wiring

For migrations:
- use the `alembic-safe-migration` skill
- use the `migration` agent for anything with rollout risk

For contract changes:
- use the `api-contract-sync` skill
- rerun frontend type checks and backend tests after changing models or API responses

For risky business flows:
- use `quest-flow-regression`
- run regression checks before considering the change done

For runtime incidents:
- use `live-runtime-debug`
- verify backend health first, then worker/scheduler/queue state, then rerun the failing verification signal