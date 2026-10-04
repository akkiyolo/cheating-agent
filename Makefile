# Unix / WSL / Git-Bash-with-make. On plain Windows use scripts/dev.ps1 (same targets).
.PHONY: install dev db backend frontend migrate test test-backend test-frontend lint format typecheck build docker docker-down clean

install:
	cd backend && uv sync
	cd mock-assessment && npm ci

db:
	docker compose up -d db

migrate:
	cd backend && uv run alembic upgrade head

backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:
	cd mock-assessment && npm run dev

dev: db
	$(MAKE) -j2 backend frontend

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest -q

test-frontend:
	cd mock-assessment && npm test

lint:
	cd backend && uv run ruff check .
	cd mock-assessment && npm run lint && npx prettier --check src

format:
	cd backend && uv run ruff check --fix .
	cd mock-assessment && npm run format

typecheck:
	cd backend && uv run mypy app
	cd mock-assessment && npx tsc -b

build:
	cd mock-assessment && npm run build

docker:
	docker compose up -d --build

docker-down:
	docker compose down

clean:
	rm -rf mock-assessment/dist mock-assessment/*.tsbuildinfo backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
