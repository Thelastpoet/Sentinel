.PHONY: run test contract lint format typecheck precommit-install precommit-run up down seed-lexicon apply-migrations test-db release-list release-create release-ingest release-activate release-deprecate release-validate release-audit benchmark-hot-path worker-once eval-language connector-ingest verify-tier2-wave1 go-live-check

LIMIT ?= 20
ITERATIONS ?= 300
WARMUP ?= 30
P95_BUDGET_MS ?= 150
BUNDLE_DIR ?= templates/go-live

run:
	python -m uvicorn sentinel_api.main:app --reload

test:
	python -m pytest -q

contract:
	python scripts/check_contract.py

lint:
	python -m ruff check src scripts tests

format:
	python -m ruff format src scripts tests

typecheck:
	python -m pyright

precommit-install:
	python -m pre_commit install

precommit-run:
	python -m pre_commit run --all-files

up:
	docker compose up --build

down:
	docker compose down -v

seed-lexicon:
	python scripts/sync_lexicon_seed.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel --activate-if-none

apply-migrations:
	python scripts/apply_migrations.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel

test-db:
	SENTINEL_INTEGRATION_DB_URL=postgresql://sentinel:sentinel@localhost:5432/sentinel python -m pytest -q tests/test_lexicon_postgres_integration.py

release-list:
	python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel list

release-create:
	python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel create --version "$(VERSION)"

release-ingest:
	python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel ingest --version "$(VERSION)" --input-path "$(INPUT)"

release-activate:
	python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel activate --version "$(VERSION)"

release-deprecate:
	python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel deprecate --version "$(VERSION)"

release-validate:
	python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel validate --version "$(VERSION)"

release-audit:
	python scripts/manage_lexicon_release.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel audit --limit "$(LIMIT)"

benchmark-hot-path:
	python scripts/benchmark_hot_path.py --iterations "$(ITERATIONS)" --warmup "$(WARMUP)" --p95-budget-ms "$(P95_BUDGET_MS)"

worker-once:
	python scripts/run_async_worker.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel --max-items 20

eval-language:
	python scripts/evaluate_language_packs.py --input-path "$(INPUT)" --pretty

connector-ingest:
	python scripts/run_partner_connector_ingest.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel --connector-name "$(CONNECTOR)" --input-path "$(INPUT)"

verify-tier2-wave1:
	python scripts/verify_tier2_wave1.py --registry-path data/langpacks/registry.json --pretty

go-live-check:
	python scripts/check_go_live_readiness.py --bundle-dir "$(BUNDLE_DIR)"
