# Single-image deployment (Render, or any container host): builds the front end and serves it from the same
# FastAPI process as the API (front end at "/", API under "/api"). Migrations run on start-up.
#
# There is no Docker daemon inside this image, so the code judge is unavailable here: "Run sample tests"
# returns 503 and coding answers are recorded but scored 0 with an explanatory error. Use docker-compose.yml
# on a host with Docker if you need the judge.

FROM node:20-alpine AS web
WORKDIR /src
COPY mock-assessment/package.json mock-assessment/package-lock.json ./
RUN npm ci
COPY mock-assessment/ ./
RUN npm run build

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
RUN uv sync --frozen --no-dev

COPY --from=web /src/dist /app/static
RUN useradd --system --uid 10001 app
USER app

ENV ENV=prod FRONTEND_DIST=/app/static
EXPOSE 10000
# Render injects PORT (default 10000); fall back to 8000 elsewhere.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
