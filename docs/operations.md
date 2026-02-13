# Sentinel Operations Runbook

This runbook contains operational commands and environment knobs for local/dev and staging operations.

## Core make targets

```bash
make run
make up
make down
make test
make contract
make lint
make typecheck
make precommit-install
make precommit-run
make apply-migrations
make seed-lexicon
```

## Environment setup (pip)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev,ops]
export SENTINEL_API_KEY='replace-with-strong-api-key'
```

`SENTINEL_API_KEY` is required. There is no built-in fallback key.

## Manual migration and seed sync

```bash
python scripts/apply_migrations.py --database-url "$SENTINEL_DATABASE_URL"
python scripts/sync_lexicon_seed.py --database-url "$SENTINEL_DATABASE_URL" --activate-if-none
```

## Lexicon backend behavior

- Postgres is preferred when `SENTINEL_DATABASE_URL` is set.
- File fallback is `data/lexicon_seed.json`.
- Hot-trigger cache uses Redis via `SENTINEL_REDIS_URL`.
- Semantic match uses pgvector when migration `0007_lexicon_entry_embeddings.sql` is present.
- Optional semantic threshold override: `SENTINEL_VECTOR_MATCH_THRESHOLD`.

## Lexicon release governance

```bash
make release-list
make release-create VERSION=hatelex-v2.2
make release-ingest VERSION=hatelex-v2.2 INPUT=data/lexicon_seed.json
make release-validate VERSION=hatelex-v2.2
make release-activate VERSION=hatelex-v2.2
make release-deprecate VERSION=hatelex-v2.1
make release-audit LIMIT=20
```

Legal hold helpers:

```bash
python scripts/manage_lexicon_release.py --database-url "$SENTINEL_DATABASE_URL" --actor ops hold --version hatelex-v2.2 --reason "legal request"
python scripts/manage_lexicon_release.py --database-url "$SENTINEL_DATABASE_URL" --actor ops holds --limit 20
python scripts/manage_lexicon_release.py --database-url "$SENTINEL_DATABASE_URL" --actor ops unhold --version hatelex-v2.2 --reason "case closed"
```

## Runtime metrics

```bash
curl -sS http://localhost:8000/metrics; echo
curl -sS http://localhost:8000/metrics/prometheus
```

Returns action/status counts, validation errors, and latency buckets.

## Benchmark and evaluation

```bash
python scripts/benchmark_hot_path.py --iterations 300 --warmup 30 --p95-budget-ms 150
python scripts/evaluate_language_packs.py --input-path data/eval/sample_eval.jsonl --pretty
python scripts/verify_tier2_wave1.py --registry-path data/langpacks/registry.json --pretty
```

## Go-live readiness gate

Prepare a release bundle by copying:

- `docs/releases/go-live/template/` -> `docs/releases/go-live/<release-id>/`

Then validate:

```bash
python scripts/check_go_live_readiness.py --bundle-dir docs/releases/go-live/<release-id>
```

## Async worker

```bash
python scripts/run_async_worker.py \
  --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel \
  --worker-id ops-worker-1 \
  --max-items 20 \
  --error-retry-seconds 120 \
  --max-retry-attempts 5 \
  --max-error-retry-seconds 3600
```

## Partner connector ingest

```bash
python scripts/run_partner_connector_ingest.py \
  --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel \
  --connector-name partner-factcheck \
  --input-path data/partner_signals.jsonl \
  --limit 200 \
  --max-attempts 3 \
  --base-backoff-seconds 2 \
  --max-backoff-seconds 60 \
  --circuit-failure-threshold 3 \
  --circuit-reset-seconds 120
```

## Policy runtime environment

- `SENTINEL_POLICY_CONFIG_PATH`: override policy config path.
- `SENTINEL_DEPLOYMENT_STAGE`: `shadow|advisory|supervised`.
- `SENTINEL_ELECTORAL_PHASE`: `pre_campaign|campaign|silence_period|voting_day|results_period`.

## `model_version` provenance

- `model_version` in moderation responses identifies the active inference artifact
  set used for that decision.
- The value is audit/provenance metadata and can refer to deterministic heuristic
  paths, learned model artifacts, or a governed combination.
- For appeals and transparency workflows, persist the exact emitted
  `original_model_version` value unchanged.

## Rate limiting environment

- `SENTINEL_RATE_LIMIT_PER_MINUTE`: default `120`.
- `SENTINEL_RATE_LIMIT_STORAGE_URI`: distributed backend URI for `limits` (for example `redis://redis:6379/0`).
  if unset, falls back to in-memory limiter.

## OAuth scope setup (internal/admin)

OAuth bearer auth has no built-in default tokens. Configure one of:

- `SENTINEL_OAUTH_TOKENS_JSON` for static token registry in controlled environments.
- `SENTINEL_OAUTH_JWT_SECRET` (+ optional audience/issuer) for JWT validation.

Example token registry payload:

```bash
export SENTINEL_OAUTH_TOKENS_JSON='{
  "ops-token": {
    "client_id": "ops-service",
    "scopes": [
      "internal:queue:read",
      "admin:proposal:read",
      "admin:proposal:review",
      "admin:appeal:read",
      "admin:appeal:write",
      "admin:transparency:read",
      "admin:transparency:export",
      "admin:transparency:identifiers"
    ]
  }
}'
```

Internal/admin endpoint scope map is implemented in `src/sentinel_api/main.py` and `src/sentinel_api/oauth.py`.

JWT mode (production-oriented) can be enabled instead of static token registry:

```bash
export SENTINEL_OAUTH_JWT_SECRET='replace-with-strong-secret'
export SENTINEL_OAUTH_JWT_ALGORITHM='HS256'
# optional
export SENTINEL_OAUTH_JWT_AUDIENCE='sentinel-internal'
export SENTINEL_OAUTH_JWT_ISSUER='sentinel-auth'
```
