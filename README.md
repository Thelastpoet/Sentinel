# Sentinel

Kenya-native multilingual political-safety infrastructure designed to help protect the 2027 General Election from ethnic incitement and election-related disinformation.

Sentinel provides:

- a real-time Moderation API (`/v1/moderate`) for low-latency publishing workflows;
- an async monitoring/update pipeline for partner signals, queueing, and governed lexicon updates;
- deterministic governance primitives: versioned policies, release lifecycle, appeals, transparency exports, and audit trails.

## Project status

Current status: **active development, not yet broad customer production launch**.

Core implementation phases are complete through `I-407`. Final go-live hardening is tracked in:

- `docs/specs/tasks.md` (`I-408` through `I-412`)
- `docs/specs/phase4/i408-go-live-readiness-gate.md`

## Core capabilities

- Deterministic moderation response contract with evidence and reason codes.
- Span-level language routing for code-switched text.
- Redis hot-trigger matching and Postgres/pgvector semantic retrieval.
- Electoral phase modes and deployment-stage controls (`shadow`, `advisory`, `supervised`).
- Appeals workflow, case reconstruction, transparency reporting/export.
- Partner connector ingestion with retry, exponential backoff, and circuit breaker.
- Tier-2 Wave 1 language-pack gate verification (Luo, Kalenjin).

## Quickstart

### Local (pip)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev,ops]
python -m uvicorn sentinel_api.main:app --reload
```

### Docker Compose

```bash
docker compose up --build
make apply-migrations
make seed-lexicon
```

Health check:

```bash
curl -sS http://localhost:8000/health; echo
```

## API example

```bash
curl -sS -X POST http://localhost:8000/v1/moderate \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-key' \
  -d '{"text":"They should kill them now."}'
```

## Quality checks

```bash
python -m pytest -q
python scripts/check_contract.py
python scripts/benchmark_hot_path.py --iterations 300 --warmup 30 --p95-budget-ms 150
python scripts/verify_tier2_wave1.py --registry-path data/langpacks/registry.json --pretty
```

Prometheus/OpenMetrics scrape endpoint:

```bash
curl -sS http://localhost:8000/metrics/prometheus
```

Pre-commit hooks:

```bash
python -m pre_commit install
python -m pre_commit run --all-files
```

## Specs and architecture

- Master plan: `docs/master.md`
- Task board: `docs/specs/tasks.md`
- OpenAPI: `docs/specs/api/openapi.yaml`
- Public schemas: `docs/specs/schemas/`
- RFCs/ADRs: `docs/specs/rfcs/`, `docs/specs/adr/`

## Repository layout

```text
src/          runtime packages (core, router, lexicon, langpack, api)
scripts/      operational and verification tooling
migrations/   postgres schema migrations
data/         lexicon seeds, eval sets, language-pack artifacts
docs/         master plan, specs, governance, operational references
tests/        unit and integration tests
```

## Operations guide

Detailed runbook commands (release governance, async worker, connector ingest, OAuth scope setup, policy envs) are in:

- `docs/operations.md`

## Contributing and governance

- Contributor guide: `CONTRIBUTING.md`
- Code of conduct: `CODE_OF_CONDUCT.md`
- Community and governance specs: `docs/specs/governance.md`

## Security note

This repository handles election-safety workflows. Treat deployments, credentials, and incident procedures as high-risk operational assets. Follow staged rollout and go/no-go controls in `docs/specs/phase4/i408-go-live-readiness-gate.md`.

## License

Project license target is Apache-2.0 per the master plan. Add a root `LICENSE` file before public production rollout.
