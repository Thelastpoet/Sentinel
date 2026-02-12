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

## Manual migration and seed sync

```bash
uv run python scripts/apply_migrations.py --database-url "$SENTINEL_DATABASE_URL"
uv run python scripts/sync_lexicon_seed.py --database-url "$SENTINEL_DATABASE_URL" --activate-if-none
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
```

Returns action/status counts, validation errors, and latency buckets.

## Benchmark and evaluation

```bash
python scripts/benchmark_hot_path.py --iterations 300 --warmup 30 --p95-budget-ms 150
python scripts/evaluate_language_packs.py --input-path data/eval/sample_eval.jsonl --pretty
python scripts/verify_tier2_wave1.py --registry-path data/langpacks/registry.json --pretty
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

## OAuth scope setup (internal/admin)

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
