---
description: "Use when adding or changing backend tests, frontend tests, regression checks, or smoke coverage in QuestionWork. Covers minimum validation for business flows and architectural safety checks."
name: "QuestionWork Tests"
applyTo:
  - "backend/tests/**/*.py"
  - "frontend/src/**/*.test.ts"
  - "frontend/src/**/*.test.tsx"
  - "frontend/src/**/*.spec.ts"
  - "frontend/src/**/*.spec.tsx"
---
# QuestionWork Tests

- Prefer focused tests that validate business behavior and architectural guarantees.
- For backend changes, cover success path plus the main authorization or validation failure.
- For money, escrow, XP, withdrawals, disputes, or quest-state changes, add regression coverage.
- Reuse existing fixtures and test patterns before introducing new harness code.
- Keep smoke checks lightweight and deterministic.
