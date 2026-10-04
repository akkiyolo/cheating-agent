# Mock Assessment Platform

A self-hosted online assessment platform: a FastAPI backend that generates a fresh, randomised question set for
every session, grades it on the server, and judges code submissions in a locked-down Docker sandbox; plus a
React front end (in progress) for candidates.

> **Scope note.** This repository was originally started with the goal of building an autonomous agent that
> completes online assessments. That part was **not built** and is not part of this project. What exists is
> the assessment platform itself, described below.

## Status

| Component | State |
|---|---|
| Backend API (auth, assessments, sessions, answers, review, submit, results) | Working, tested |
| Randomised question bank (MCQ, true/false, multi-select, numerical, text, image, table, coding) | Working, tested |
| Server-side grading, incl. hidden coding tests | Working, tested |
| Docker code sandbox / judge (Python, C++, Java) | Working, tested |
| Front end: login, instructions, assessment, review, submitted, results | Working, tested |
| Alembic migrations | Not implemented (`alembic/` is empty; dev/test use `create_all`) |
| Docker Compose, Makefile, CI | Not implemented |

Last full test run: **79 passed** backend (`uv run pytest`), **6 passed** front end (`npm test`); `npm run build` and `npm run lint` clean.

## Repository layout

```
backend/
  app/
    api/          auth.py, assessments.py, code.py, deps.py   (HTTP routes)
    models/       user.py, assessment.py, types.py            (SQLAlchemy 2.x async ORM)
    services/     auth.py, assessment_service.py, grading.py,
                  question_bank.py, images.py                 (domain logic)
    sandbox/      runner.py                                   (Docker code judge)
    config.py     settings from env / .env (frozen)
    db.py         engine + session management
    main.py       FastAPI app, seeds users + default assessment
  tests/          unit/ and integration/ (pytest, pytest-asyncio)
mock-assessment/  React 19 + TypeScript + Vite + Tailwind 4 + TanStack Query + Zustand
```

## Backend

### Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- PostgreSQL (default URL points at `localhost:5433`) — or SQLite for local hacking
- Docker, for the code sandbox

### Run

```bash
cd backend
uv sync
# SQLite instead of Postgres for a quick local run:
DATABASE_URL=sqlite+aiosqlite:///./dev.db uv run uvicorn app.main:app --reload --port 8000
```

On start-up (non-prod) the app creates tables and seeds three users and one assessment
(`general-aptitude`, 21 questions).

| User | Default password | Role |
|---|---|---|
| `admin` | `admin-pass` | ADMIN |
| `researcher` | `researcher-pass` | RESEARCHER |
| `candidate` | `candidate-pass` | CANDIDATE |

Change these with `ADMIN_PASSWORD`, `RESEARCHER_PASSWORD`, `CANDIDATE_PASSWORD`.

### Configuration

Read from environment variables or a `.env` file at the repo root (git-ignored). See `app/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `ENV` | `dev` | `dev` / `test` / `prod` (`prod` skips `create_all`) |
| `DATABASE_URL` | `postgresql+asyncpg://assess:assess@localhost:5433/assessment` | async SQLAlchemy URL |
| `JWT_SECRET` | dev placeholder | **set in any real deployment** |
| `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | `30` / `7` | token lifetimes |
| `CORS_ORIGINS` | `http://localhost:3000` | comma-separated |
| `ASSESSMENT_DURATION_S` | `3600` | default assessment length |
| `SANDBOX_CPUS` / `SANDBOX_MEMORY_MB` / `SANDBOX_PIDS` / `SANDBOX_TIMEOUT_S` | `0.5` / `256` / `64` / `10` | sandbox limits |
| `SANDBOX_PYTHON_IMAGE` / `SANDBOX_CPP_IMAGE` / `SANDBOX_JAVA_IMAGE` | `python:3.13-slim` / `gcc:14` / `eclipse-temurin:21-jdk` | judge images |

### API

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | username + password → access + refresh token |
| `POST` | `/auth/refresh` | rotate refresh token |
| `GET` | `/auth/me` | current user |
| `GET` | `/assessments` | list assessments |
| `POST` | `/assessments/{id or slug}/start` | start (or resume) a session |
| `GET` | `/sessions/{id}` | status, remaining time, progress |
| `GET` | `/sessions/{id}/questions` | public question view + saved responses |
| `GET` | `/sessions/{id}/questions/{uid}/image.png` | server-rendered figure for image questions |
| `POST` | `/sessions/{id}/answers` | save / revise an answer (autosave) |
| `POST` | `/sessions/{id}/review` | mark / unmark a question for review |
| `POST` | `/sessions/{id}/submit` | submit and grade |
| `GET` | `/sessions/{id}/results` | score, accuracy, per-kind and per-question breakdown |
| `POST` | `/code/run` | run code against given tests, or a question's *visible* examples |
| `GET` | `/health` | liveness |

Interactive docs: `http://localhost:8000/docs`.

### Question bank

`services/question_bank.py` defines templates; each produces a new instance per session from a seeded RNG, so
numbers, names, data and option order differ between sessions. Answer keys and template metadata are stripped
by `public_view()` before anything reaches the client; image parameters stay server-side and only a rendered
PNG is served. Coding questions ship 2–3 visible examples; the full hidden test set (including large inputs)
is computed by server-side reference solutions and used only at grading time.

Default composition: 10 MCQ/true-false, 3 numerical, 2 multi-select, 2 coding, 2 text, 1 image, 1 table.
Coding questions are worth 3 points (partial credit per hidden test passed), everything else 1.

### Code sandbox

Every run uses a fresh container with `--network none`, CPU / memory / PID limits, a read-only root filesystem
with a tmpfs `/tmp`, all capabilities dropped, `no-new-privileges`, a non-root user, per-test `timeout`, a
host-side wall-clock kill and `--rm` cleanup. Limits come from frozen settings; no API parameter can change
them. If Docker is unavailable, `/code/run` returns `503`.

### Tests

```bash
cd backend
uv run pytest            # unit + integration (SQLite in-memory)
uv run pytest -m docker  # sandbox tests only (needs Docker)
uv run ruff check . && uv run mypy app
```

## Front end (`mock-assessment/`)

```bash
cd mock-assessment
npm install
npm run dev     # http://localhost:3000, proxies /api → http://localhost:8000 (override with BACKEND_URL)
npm test        # Vitest + React Testing Library
npm run lint
```

| Route | Page |
|---|---|
| `/login` | sign in |
| `/instructions` | assessment overview and start |
| `/assessment` | one question at a time, question navigator, countdown timer, autosave (choices save immediately, typed answers after a short pause, everything is flushed before navigating), mark for review, retry banner if a save fails; coding questions get a language picker, editor and "Run sample tests" against the visible examples |
| `/review` | answered / unanswered / marked overview, jump back to any question, submit with a confirmation dialog |
| `/submitted` | confirmation |
| `/results` | score, accuracy, breakdown by question type and by question (incl. hidden-test counts for coding) |

When the timer reaches zero the session is submitted automatically (the server also enforces the deadline).
The current question position is kept in `sessionStorage`, so a page refresh resumes where you were.

`npm run build` type-checks and produces `dist/`. Node 20.17 is supported (jsdom is pinned to v25 for that).

## Security notes

- `.env` is git-ignored. Rotate any credential that has been pasted into chat logs or other shared places.
- Change `JWT_SECRET` and all seed passwords before exposing the server beyond localhost.
- Passwords are hashed with Argon2 (`pwdlib`); refresh tokens are stored as SHA-256 hashes and rotated on use.
