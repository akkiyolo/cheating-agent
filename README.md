# Mock Assessment Platform

A self-hosted online assessment platform: a FastAPI backend that generates a fresh, randomised question set for
every session, grades it on the server, and judges code submissions in a locked-down Docker sandbox; plus a
React front end for candidates. Runs locally or as a three-container Docker Compose stack.

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
| Alembic migrations (PostgreSQL) | Working; upgrade / downgrade / `alembic check` verified |
| Docker images + Compose stack (Postgres, API, nginx front end) | Working; smoke-tested incl. sandboxed code runs |
| Single-image deployment (root `Dockerfile`) + Render Blueprint (`render.yaml`) | Working; image run locally in Render-like conditions (no code judge there, see below) |
| Makefile, `scripts/dev.ps1`, GitHub Actions CI | Added; `dev.ps1` targets verified on Windows, CI not yet run on GitHub |

Last full local run: backend **85 passed** (79 of them also verified on PostgreSQL 16), `ruff` and `mypy` clean;
front end **7 passed**, `eslint`, `prettier --check`, `tsc` and `vite build` clean.

## Quick start (Docker)

```bash
cp .env.example .env          # then set JWT_SECRET to a long random string
docker compose up -d --build  # Postgres :5433, API :8000, web :3000
```

Open http://localhost:3000 and sign in as `candidate` / `candidate-pass`. The backend runs
`alembic upgrade head` on start-up. Stop with `docker compose down` (add `-v` to delete the database volume).

The backend container mounts the host Docker socket so the code judge can start sandbox containers, and shares
`/tmp/assessment-sandbox` with the host at the same path. Access to the Docker socket is root-equivalent on the
host; don't expose this backend to untrusted networks.

## Deploy to Render

The root `Dockerfile` builds one image containing both parts: the built front end is served at `/` and the API
under `/api` by the same FastAPI process (enabled by `FRONTEND_DIST`, which the image sets). Migrations run at
start-up, the server listens on `$PORT`, and it runs as a non-root user.

1. Push this repo to GitHub (already done if you're reading this there).
2. In Render: **New → Blueprint**, pick the repo. `render.yaml` creates:
   - `assessment-db`: a free PostgreSQL database
   - `assessment-platform`: a free Docker web service built from `./Dockerfile`, health check `/api/health`
3. Render generates `JWT_SECRET` and the three seed passwords. Find them under the web service's
   **Environment** tab, then sign in at `https://<service>.onrender.com`.

`DATABASE_URL` is wired from the database automatically; `postgres://` URLs are converted to the asyncpg
driver. To deploy without the Blueprint, create a Docker web service from the repo root and set `DATABASE_URL`,
`JWT_SECRET` (32+ characters) and the seed passwords yourself.

**If the deploy fails with `ENV=prod configuration error`**, the service has no environment variables. This
happens when it was created as a plain Web Service rather than from the Blueprint. Either delete it and use
**New → Blueprint**, or in the service's **Environment** tab add:

| Key | Value |
|---|---|
| `DATABASE_URL` | the **Internal Database URL** of a Render PostgreSQL database (create one first, same region) |
| `JWT_SECRET` | click **Generate** (or any random string of 32+ characters) |
| `ADMIN_PASSWORD`, `RESEARCHER_PASSWORD`, `CANDIDATE_PASSWORD` | passwords of your choice (otherwise the public defaults apply) |

then **Manual Deploy → Deploy latest commit**.

**Limits on Render:**

- **No code judge.** Render containers have no Docker daemon, so "Run sample tests" returns a clear 503 and
  coding answers are saved but shown as *Not graded (code judge unavailable)* and score 0. Every other question
  type works. For the judge, run `docker-compose.yml` on a VM with Docker instead.
- Free web services sleep when idle (the first request after a while takes ~1 minute), and Render's free
  Postgres databases expire after 30 days unless upgraded. Choose paid plans in `render.yaml` for anything real.

## Developer commands

`make <target>` on Linux/macOS/WSL, or `.\scripts\dev.ps1 <target>` on Windows:

| Target | Does |
|---|---|
| `install` | `uv sync` + `npm ci` |
| `db` | start only Postgres from Compose |
| `migrate` | `alembic upgrade head` |
| `backend` / `frontend` | dev servers on :8000 / :3000 |
| `dev` | Postgres + both dev servers |
| `test`, `test-backend`, `test-frontend` | test suites |
| `lint`, `format`, `typecheck` | ruff, eslint, prettier, mypy, tsc |
| `build` | production front-end build |
| `docker`, `docker-down` | Compose stack up / down |
| `clean` | remove build and cache output |

CI (`.github/workflows/ci.yml`) runs lint, type checks, migrations, backend tests on SQLite and PostgreSQL with
the real Docker sandbox, front-end tests and build, and a Compose image build.

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
  alembic/        migrations (alembic.ini at backend/)
  tests/          unit/ and integration/ (pytest, pytest-asyncio)
  Dockerfile
mock-assessment/  React 19 + TypeScript + Vite + Tailwind 4 + TanStack Query + Zustand (Dockerfile, nginx.conf)
scripts/dev.ps1   Windows task runner (mirrors the Makefile)
Dockerfile        single-image build (front end + API) for Render or any container host
render.yaml       Render Blueprint (web service + Postgres)
docker-compose.yml, Makefile, .env.example, .github/workflows/ci.yml
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

On start-up the app seeds three users and one assessment
(`general-aptitude`, 21 questions).

| User | Default password | Role |
|---|---|---|
| `admin` | `admin-pass` | ADMIN |
| `researcher` | `researcher-pass` | RESEARCHER |
| `candidate` | `candidate-pass` | CANDIDATE |

Change these with `ADMIN_PASSWORD`, `RESEARCHER_PASSWORD`, `CANDIDATE_PASSWORD`.

### Database and migrations

In `dev` / `test` the app calls `create_all` at start-up, so SQLite works with no setup. With `ENV=prod` (as in the
Docker image) tables are managed only by Alembic:

```bash
cd backend
uv run alembic upgrade head                      # apply
uv run alembic revision --autogenerate -m "..."  # after changing models
uv run alembic check                             # fails if models and migrations disagree
```

### Configuration

Read from environment variables or a `.env` file at the repo root (git-ignored). See `app/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `ENV` | `dev` | `dev` / `test` / `prod` (`prod` skips `create_all`) |
| `DATABASE_URL` | `postgresql+asyncpg://assess:assess@localhost:5433/assessment` | async SQLAlchemy URL |
| `JWT_SECRET` | dev placeholder | **required with `ENV=prod`** (32+ characters; start-up fails otherwise) |
| `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | `30` / `7` | token lifetimes |
| `CORS_ORIGINS` | `http://localhost:3000` | comma-separated |
| `ASSESSMENT_DURATION_S` | `3600` | default assessment length |
| `SANDBOX_CPUS` / `SANDBOX_MEMORY_MB` / `SANDBOX_PIDS` / `SANDBOX_TIMEOUT_S` | `0.5` / `256` / `64` / `10` | sandbox limits |
| `SANDBOX_PYTHON_IMAGE` / `SANDBOX_CPP_IMAGE` / `SANDBOX_JAVA_IMAGE` | `python:3.13-slim` / `gcc:14` / `eclipse-temurin:21-jdk` | judge images |
| `FRONTEND_DIST` | unset | serve this built front end at `/` and move the API under `/api` (set in the root `Dockerfile`) |
| `SANDBOX_WORKDIR` | system temp | where per-run work dirs are created (must be host-visible at the same path when the API runs in a container) |

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
