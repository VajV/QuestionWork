---
name: admin-security-audit
description: 'Audit high-risk admin and auth changes in QuestionWork. Use for TOTP, IP allowlists, admin routes, moderation actions, rate limits, and secret-handling review.'
argument-hint: 'Describe the admin or security-sensitive change'
---

# Admin Security Audit

## When to Use
- Editing admin endpoints
- Touching TOTP or IP allowlist logic
- Modifying JWT, cookies, or auth dependencies
- Reviewing bans, XP grants, withdrawals, or broadcasts

## Procedure
1. Confirm the route uses the correct auth dependency.
2. Verify rate limiting for every mutating action.
3. Check for secure defaults, especially around prod/dev settings.
4. Review logging and audit trails for sensitive operations.
5. Inspect frontend flows for any security or contract regressions.

## Done Criteria
- Permission checks are explicit
- No mutating admin path skips rate limiting
- Sensitive changes remain auditable and secure by default
