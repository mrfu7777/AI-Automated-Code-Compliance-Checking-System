.PHONY: bootstrap up down logs api-test api-lint web-test web-lint web-build check migrate

bootstrap:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	docker compose -f infra/docker-compose.yml build

up:
	docker compose -f infra/docker-compose.yml up --build

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

migrate:
	docker compose -f infra/docker-compose.yml run --rm api alembic upgrade head

api-test:
	docker compose -f infra/docker-compose.yml run --rm api pytest

api-lint:
	docker compose -f infra/docker-compose.yml run --rm api ruff check .
	docker compose -f infra/docker-compose.yml run --rm api mypy app

web-test:
	docker compose -f infra/docker-compose.yml run --rm web npm run test

web-lint:
	docker compose -f infra/docker-compose.yml run --rm web npm run lint

web-build:
	docker compose -f infra/docker-compose.yml run --rm web npm run build

check: api-lint api-test web-lint web-test web-build
