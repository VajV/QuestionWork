# CI Workflows

## `ci.yml` — Continuous Integration

Runs on every push to `main`/`develop` and on pull requests targeting `main`.  
Both jobs run **in parallel**.

### `backend-tests`

| Step | Description |
|------|-------------|
| Setup Python 3.12 | Installs the Python runtime |
| Cache pip | Caches `~/.cache/pip` keyed on `backend/requirements.txt` |
| Install deps | `pip install -r backend/requirements.txt` |
| pytest | `pytest tests/ --no-cov -x -q --tb=short` — fails fast on first error, no coverage overhead |

### `frontend-check`

| Step | Description |
|------|-------------|
| Setup Node 20 | Installs the Node.js runtime |
| Cache node_modules | Caches `frontend/node_modules` keyed on `package-lock.json` |
| npm ci | Clean install from lockfile |
| ESLint | `npm run lint` — enforces code style rules |
| TypeScript | `npx tsc --noEmit` — type-checks without emitting files |
| Next.js build | `npm run build` — verifies the production bundle compiles |

## `copilot-customizations.yml` — Customization Validation

Runs whenever workspace Copilot customizations change.

| Step | Description |
|------|-------------|
| Setup Python 3.12 | Installs the validation runtime |
| Validate customizations | Runs `python scripts/validate_copilot_customizations.py` to ensure native instructions, skills, prompts, agents, hooks, and MCP config are present and parseable |

