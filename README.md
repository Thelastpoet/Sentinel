# Project Sentinel

Spec-driven implementation scaffold for the Sentinel Moderation API.

## Run

```bash
uv sync
uv run uvicorn sentinel_api.main:app --reload
```

Or with Docker:

```bash
docker compose up --build
make seed-lexicon
```

Shortcuts:

```bash
make run
make up
make seed-lexicon
```

## Test

```bash
uv run pytest
```

Contract check:

```bash
python scripts/check_contract.py
```

`POST /v1/moderate` error responses are standardized as `ErrorResponse` for
`400`, `401`, `429`, and `500` statuses.
Successful moderation responses include rate-limit headers:
`X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`.
Throttled responses (`429`) also include `Retry-After`.

Shortcuts:

```bash
make test
make contract
```

## Spec references

- `docs/specs/api/openapi.yaml`
- `docs/specs/schemas/moderation-request.schema.json`
- `docs/specs/schemas/moderation-response.schema.json`
- `docs/specs/rfcs/0001-v1-moderation-api.md`

## Lexicon backends

- The API prefers Postgres when `SENTINEL_DATABASE_URL` is set.
- If Postgres is unavailable or empty, it falls back to `data/lexicon_seed.json`.

For manual database setup (outside Docker init), apply:

```bash
uv run python scripts/apply_migrations.py --database-url "$SENTINEL_DATABASE_URL"
uv run python scripts/sync_lexicon_seed.py --database-url "$SENTINEL_DATABASE_URL" --activate-if-none
```

Or with project shortcuts:

```bash
make apply-migrations
make seed-lexicon
make test-db
```

## Lexicon release governance

Manage release states with:

```bash
make release-list
make release-create VERSION=hatelex-v2.2
make release-ingest VERSION=hatelex-v2.2 INPUT=data/lexicon_seed.json
make release-validate VERSION=hatelex-v2.2
make release-activate VERSION=hatelex-v2.2
make release-deprecate VERSION=hatelex-v2.1
make release-audit LIMIT=20
python scripts/manage_lexicon_release.py --database-url "$SENTINEL_DATABASE_URL" --actor ops hold --version hatelex-v2.2 --reason "legal request"
python scripts/manage_lexicon_release.py --database-url "$SENTINEL_DATABASE_URL" --actor ops holds --limit 20
python scripts/manage_lexicon_release.py --database-url "$SENTINEL_DATABASE_URL" --actor ops unhold --version hatelex-v2.2 --reason "case closed"
```

Ingest input accepts either:

- a JSON list of entries, or
- an object with an `entries` list (same shape as `data/lexicon_seed.json`).

## Runtime metrics

Read in-memory counters:

```bash
curl -sS http://localhost:8000/metrics; echo
```

Response includes action/status counters, `validation_error_count`, and
`latency_ms_buckets` for moderation request latency distribution.

## Latency benchmark

Run reproducible hot-path latency benchmark (local process):

```bash
python scripts/benchmark_hot_path.py --iterations 300 --warmup 30 --p95-budget-ms 150
```

Make shortcut:

```bash
make benchmark-hot-path ITERATIONS=300 WARMUP=30 P95_BUDGET_MS=150
```

## Policy config

- Default policy config path: `config/policy/default.json`
- Override path with environment variable: `SENTINEL_POLICY_CONFIG_PATH`

## OAuth scopes for internal/admin APIs (S1)

Internal/admin endpoints use Bearer tokens with scope checks:

- `GET /internal/monitoring/queue/metrics` -> `internal:queue:read`
- `GET /admin/release-proposals/permissions` -> `admin:proposal:read`
- `POST /admin/release-proposals/{proposal_id}/review` -> `admin:proposal:review`

Configure token registry with `SENTINEL_OAUTH_TOKENS_JSON`:

```bash
export SENTINEL_OAUTH_TOKENS_JSON='{
  "ops-token": {
    "client_id": "ops-service",
    "scopes": ["internal:queue:read", "admin:proposal:read", "admin:proposal:review"]
  }
}'
```
