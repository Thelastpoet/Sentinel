.PHONY: run test contract up down seed-lexicon apply-migrations test-db release-list release-create release-ingest release-activate release-deprecate release-validate release-audit benchmark-hot-path

LIMIT ?= 20
ITERATIONS ?= 300
WARMUP ?= 30
P95_BUDGET_MS ?= 150

run:
	uv run uvicorn sentinel_api.main:app --reload

test:
	uv run pytest -q

contract:
	uv run python scripts/check_contract.py

up:
	docker compose up --build

down:
	docker compose down -v

seed-lexicon:
	uv run python scripts/sync_lexicon_seed.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel --activate-if-none

apply-migrations:
	uv run python scripts/apply_migrations.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel

test-db:
	SENTINEL_INTEGRATION_DB_URL=postgresql://sentinel:sentinel@localhost:5432/sentinel uv run pytest -q tests/test_lexicon_postgres_integration.py

release-list:
	uv run python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel list

release-create:
	uv run python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel create --version "$(VERSION)"

release-ingest:
	uv run python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel ingest --version "$(VERSION)" --input-path "$(INPUT)"

release-activate:
	uv run python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel activate --version "$(VERSION)"

release-deprecate:
	uv run python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel deprecate --version "$(VERSION)"

release-validate:
	uv run python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel validate --version "$(VERSION)"

release-audit:
	uv run python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel audit --limit "$(LIMIT)"

benchmark-hot-path:
	uv run python scripts/benchmark_hot_path.py --iterations "$(ITERATIONS)" --warmup "$(WARMUP)" --p95-budget-ms "$(P95_BUDGET_MS)"
