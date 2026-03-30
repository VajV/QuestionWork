---
description: "Use when editing admin endpoints, TOTP flows, IP allowlist logic, moderation features, auth dependencies, or security-sensitive QuestionWork code. Covers require_admin, rate limiting, auditability, and safe defaults."
name: "QuestionWork Admin Security"
---
# QuestionWork Admin Security

- Admin routes should require `require_admin` and preserve existing permission boundaries.
- Mutating admin operations still need explicit `check_rate_limit()`.
- Preserve auditability for bans, XP grants, wallet actions, withdrawals, broadcasts, and dispute actions.
- Treat TOTP, IP allowlist, auth cookies, JWT handling, and secret defaults as high-risk areas.
- Prefer secure defaults over convenience defaults, especially for production-like settings.
