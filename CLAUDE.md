# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QuestionWork — IT freelance marketplace with RPG gamification. Full-stack monorepo: Next.js frontend + FastAPI backend. Freelancers take "quests" (tasks), earn XP, level up through grades (Novice → Junior → Middle → Senior).

## Commands

### Backend
```bash
cd backend
.venv/Scripts/activate        # activate venv (Windows)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001   # dev server
```
- Swagger docs: http://localhost:8001/docs
- Setup script: `backend/scripts/setup.ps1`

### Frontend
```bash
cd frontend
npm run dev      # dev server on :3000
npm run build    # production build
npm run lint     # ESLint
```
- Setup script: `frontend/scripts/setup.ps1`

### Integration Tests
PowerShell scripts in `scripts/` — `test-full-flow.ps1` runs the complete E2E flow. Other scripts test individual flows (auth, quests, apply, completion).

## Architecture

**Backend** (`backend/app/`):
- `api/v1/endpoints/` — FastAPI route handlers (auth, quests, users)
- `api/v1/api.py` — router aggregation
- `core/security.py` — JWT (HS256) + bcrypt password hashing
- `core/rewards.py` — XP calculation, level-up logic
- `core/config.py` — pydantic-settings from `.env`
- `models/` — Pydantic models for User (with RPG stats/badges) and Quest (with application system)
- `main.py` — app init, CORS config, health endpoint

Currently uses **in-memory mock storage** (dicts in endpoint files). Database (PostgreSQL via asyncpg) and Redis are in requirements but not yet wired up.

**Frontend** (`frontend/src/`):
- Next.js 14 App Router (`app/` directory)
- `context/AuthContext` — auth state via React Context + localStorage token persistence
- `lib/api.ts` — centralized API client with auto Bearer token injection
- `components/rpg/` — RPG-specific UI (LevelBadge, StatsPanel)
- `components/quests/` — quest marketplace components
- Tailwind CSS + Framer Motion for styling/animations

**API contract**: Frontend calls `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8001/api/v1`). Auth uses Bearer JWT tokens in Authorization header.

## Key Patterns

- All API routes versioned under `/api/v1/`
- Auth endpoints return JWT; protected endpoints use `get_current_user` dependency
- Quest lifecycle: open → in_progress → completed/cancelled, with application/assign flow
- User progression: XP gain on quest completion triggers level-up checks in `core/rewards.py`
- Frontend uses TypeScript throughout; types defined in `src/types/`
