.PHONY: seed-demo migrate up down test dev-api dev-web install-web quality lint-api test-api migration-heads check-web

seed-demo:
	cd apps/api && python seed.py

migrate:
	cd apps/api && alembic upgrade head

up:
	docker compose up -d

down:
	docker compose down

test:
	cd apps/api && python -m pytest tests/ -v

test-api:
	cd apps/api && python -m pytest tests/ -v --tb=short

lint-api:
	cd apps/api && ruff check .
	cd apps/api && ruff format --check .

migration-heads:
	@cd apps/api && test "$$(alembic heads | grep -c '(head)')" -eq 1 || (echo "Expected exactly one Alembic head" && alembic heads && exit 1)

check-web:
	cd apps/web && npm run type-check
	cd apps/web && npm run lint
	cd apps/web && npm run build

quality: lint-api migration-heads test-api check-web

install-web:
	cd apps/web && npm install

dev-api:
	cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	cd apps/web && npm run dev
