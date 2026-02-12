# Repository Guidelines

## Project Structure & Module Organization

- `src/sentinel_api/`: FastAPI service code (API handlers, policy engine, lexicon repositories, rate limiting, metrics).
- `tests/`: Unit and integration tests (`test_api.py`, lexicon/release workflow tests, Postgres integration tests).
- `scripts/`: Operational tooling (contract checks, migrations, seed sync, release management).
- `migrations/`: Ordered SQL migrations (`0001_...sql`, `0002_...sql`).
- `docs/master.md`: Strategic project blueprint.
- `docs/specs/`: Spec-first source of truth (RFCs, ADRs, OpenAPI, JSON schemas, task board).
- `data/lexicon_seed.json`: Local fallback lexicon seed.

## Build, Test, and Development Commands

- `source .venv/bin/activate`: Activate local environment.
- `make run`: Start API locally (`uvicorn sentinel_api.main:app --reload`).
- `make test`: Run full test suite.
- `make contract`: Validate OpenAPI/schema consistency.
- `make up` / `make down`: Start/stop Docker stack (API + Postgres + Redis).
- `make apply-migrations`: Apply all SQL migrations to local Postgres.
- `make seed-lexicon`: Seed lexicon data and activate first release if none exists.
- `make test-db`: Run DB-backed integration tests.

## Coding Style & Naming Conventions

- Python 3.12+, 4-space indentation, type hints required for new code.
- Prefer small, focused modules; keep business logic out of route handlers.
- File names: `snake_case.py`; tests: `test_*.py`.
- Migration files must be ordered (`000N_descriptive_name.sql`).
- Keep response contracts deterministic and aligned with `docs/specs/api/openapi.yaml`.

## Testing Guidelines

- Framework: `pytest`.
- Add/adjust tests for every behavior change (unit + integration as needed).
- Keep contract guarantees green: run `python scripts/check_contract.py`.
- DB-specific tests should be isolated in dedicated files and runnable with an explicit DB URL.

## Commit & Pull Request Guidelines

- This workspace may not include full Git history; use Conventional Commit style (e.g., `feat:`, `fix:`, `docs:`).
- PRs should include:
  - linked task ID from `docs/specs/tasks.md`,
  - spec references (RFC/ADR/OpenAPI/schema),
  - test evidence (`pytest` + contract check),
  - migration notes when schema changes are included.

## Security & Configuration Tips

- Use environment variables (`SENTINEL_API_KEY`, `SENTINEL_DATABASE_URL`, `SENTINEL_LEXICON_PATH`).
- Never hardcode secrets in code, tests, or docs.
- Validate release readiness before activation: `make release-validate VERSION=<version>`.
