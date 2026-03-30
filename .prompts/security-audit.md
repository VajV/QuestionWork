# Prompt: Security Audit

Use this checklist to perform a security audit of QuestionWork (or a specific PR/feature).
Work through each section systematically. Flag every finding with a severity:
**CRITICAL** / **HIGH** / **MEDIUM** / **LOW** / **INFO**.

---

## 1. SQL Injection

**Rule**: All DB queries must use asyncpg positional parameters (`$1`, `$2`, …).
**Never** build SQL with f-strings, `.format()`, or `%` interpolation.

```bash
# Find suspicious SQL construction in services:
grep -rn "f\".*SELECT\|f\".*INSERT\|f\".*UPDATE\|f\".*DELETE\|format.*SELECT" \
  backend/app/services/ backend/app/api/
```

Red flags:
- `f"SELECT * FROM users WHERE id = '{user_id}'"` → **CRITICAL**
- `"SELECT * FROM " + table_name` → **CRITICAL**
- Dynamic ORDER BY without whitelist validation → **HIGH**

Safe pattern:
```python
await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
```

---

## 2. Authentication & Authorization

### 2a. Endpoint protection
Every non-public endpoint must declare a `Depends(require_auth)` or `Depends(require_admin)`.

```bash
# Find routes missing auth dependency:
grep -n "@router\." backend/app/api/v1/endpoints/*.py | grep -v "login\|register\|health"
# Then check that each has Depends(require_auth) or Depends(require_admin)
```

### 2b. Admin-only endpoints
Any endpoint that modifies other users' data, grants roles, or accesses aggregate reports
must use `Depends(require_admin)`, not just `require_auth`.

### 2c. JWT configuration
Check `backend/app/core/security.py`:
- Algorithm must be `HS256` (asymmetric RS256 is better for future, but HS256 is current)
- `SECRET_KEY` must come from env, never hardcoded
- Access token expiry should be ≤ 30 minutes
- Refresh token must be httpOnly cookie (never in response body)

### 2d. Token storage (frontend)
```bash
grep -rn "localStorage.*token\|sessionStorage.*token" frontend/src/
```
- Any match outside of a comment is **HIGH** — tokens must live in JS module variable only

---

## 3. Input Validation

### 3a. Pydantic field constraints
Every user-controlled string field should have `max_length`. Check for fields with no constraints:
```bash
grep -n "str$\|Optional\[str\]$" backend/app/models/*.py backend/app/schemas/*.py
```

### 3b. Numeric bounds
Integer fields (XP amounts, prices, quantities) should have `ge=0` or `gt=0`:
```bash
grep -n "int$\|Optional\[int\]$" backend/app/models/*.py
```

### 3c. File uploads
If any endpoint accepts file uploads — validate MIME type server-side, not just extension.
Limit file size. Store outside webroot.

---

## 4. Rate Limiting

**Rule**: All POST, PATCH, DELETE endpoints must call `check_rate_limit()`.

```bash
# Find mutating routes:
grep -n "@router\.post\|@router\.patch\|@router\.delete" \
  backend/app/api/v1/endpoints/*.py

# For each, verify check_rate_limit is called in the handler body
grep -n "check_rate_limit" backend/app/api/v1/endpoints/*.py
```

Missing rate limit on auth endpoints (login, reset-password) is **HIGH**.
Missing on regular mutation endpoints is **MEDIUM**.

---

## 5. Secrets & Configuration

```bash
# Scan for hardcoded secrets:
grep -rn "SECRET_KEY\s*=\s*['\"]" backend/
grep -rn "password\s*=\s*['\"]" backend/app/
grep -rn "DATABASE_URL\s*=\s*['\"]postgres" backend/app/

# Check .env is gitignored:
cat .gitignore | grep -i env
```

Red flags:
- Any secret literal in Python source → **CRITICAL**
- `.env` committed to git → **CRITICAL**
- Default/weak `SECRET_KEY` (< 32 chars) → **HIGH**

---

## 6. CORS Configuration

Check `backend/app/main.py` CORSMiddleware:
- `allow_origins` must NOT be `["*"]` in production
- Production origins should be the exact frontend URL(s)
- `allow_credentials=True` requires explicit (non-wildcard) origins

```bash
grep -n "CORSMiddleware\|allow_origins\|allow_credentials" backend/app/main.py
```

---

## 7. Financial Logic

**Rule**: All money calculations must use `Decimal` with `ROUND_HALF_UP`.

```bash
# Find float usage near financial fields:
grep -rn "float\|0\.1\|0\.15\|0\.2" backend/app/services/wallet_service.py \
  backend/app/services/commission*.py
```

- Any `float` in commission/reward/balance code → **HIGH**
- Integer arithmetic on cent values (safe) → **INFO**

---

## 8. Sensitive Data Exposure

### 8a. Password fields
Pydantic response models must never include `password_hash` or `hashed_password`:
```bash
grep -rn "password_hash\|hashed_password" backend/app/models/
```

### 8b. Logging
No `print()` or `logger.*` calls should log user passwords, tokens, or PII:
```bash
grep -rn "print\|logger\." backend/app/ | grep -i "password\|token\|secret"
```

### 8c. Error messages
500 errors must not expose stack traces to clients. Check FastAPI exception handlers in `main.py`.

---

## 9. Dependency Vulnerabilities

```bash
# Check Python dependencies:
cd backend && .venv/Scripts/python.exe -m pip audit
# Or: .venv/Scripts/python.exe -m safety check

# Check npm dependencies:
cd frontend && npm audit --audit-level=high
```

---

## 10. Frontend XSS

- `dangerouslySetInnerHTML` usage → verify source is sanitized
- User-controlled URLs in `href` → must validate scheme (reject `javascript:`)
- Content-Security-Policy header configured in `next.config.mjs`?

```bash
grep -rn "dangerouslySetInnerHTML\|javascript:" frontend/src/
grep -n "Content-Security-Policy\|headers" frontend/next.config.mjs
```

---

## Audit Summary Template

After completing all sections, report using this format:

```
## Security Audit Results — <date>

### CRITICAL (fix immediately)
- [ ] <finding>: <file>:<line> — <description>

### HIGH (fix before next release)
- [ ] <finding>: <file>:<line> — <description>

### MEDIUM (fix in current sprint)
- [ ] <finding>: <file>:<line> — <description>

### LOW / INFO
- [ ] <finding>: <description>

### Clean (no issues found)
- SQL parameterization: ✅
- Auth coverage: ✅
- Rate limiting: ✅
- Secret management: ✅
- CORS: ✅
- Financial Decimal usage: ✅
- Dependency CVEs: ✅
```
