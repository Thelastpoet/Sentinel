# Deployment Guide

This guide is for operators deploying and managing a Sentinel instance. It covers infrastructure, configuration, database setup, lexicon management, electoral phases, deployment stages, OAuth, and monitoring.

## Architecture overview

Sentinel has three runtime components:

```
┌─────────────┐     ┌──────────────────┐     ┌─────────┐
│  Your App   │────>│  Sentinel API    │────>│ Postgres │
│  (client)   │<────│  (FastAPI)       │<────│ pgvector │
└─────────────┘     │                  │     └──────────┘
                    │                  │────>┌─────────┐
                    └──────────────────┘<────│  Redis   │
                                            └──────────┘
```

- **Sentinel API** — FastAPI application serving moderation, admin, and monitoring endpoints
- **PostgreSQL with pgvector** — Stores lexicon entries, releases, embeddings, appeals, transparency data, model artifacts. Required for production.
- **Redis** — Distributed rate limiting and hot-trigger caching. Optional; Sentinel degrades gracefully if unavailable.

Default moderation routing is active for `en`, `sw`, and `sh`. Additional language-pack artifacts may exist in the repository for staged rollout but are not automatically active in hot-path enforcement.

Without Postgres, Sentinel runs in file-based fallback mode (lexicon loaded from `data/lexicon_seed.json`, appeals stored in-memory). This is suitable for development but not production.

## Environment variables

This section focuses on API runtime and operator-facing variables. A few script-only actor variables are intentionally omitted.

### Core

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTINEL_API_KEY` | Yes | — | API key for authenticating `POST /v1/moderate` requests |
| `SENTINEL_DATABASE_URL` | No | — | Postgres connection string (e.g., `postgresql://user:pass@host:5432/sentinel`). Enables lexicon DB, vector search, appeals, transparency. |
| `SENTINEL_REDIS_URL` | No | — | Redis connection string. Enables distributed rate limiting and hot-trigger caching. |
| `SENTINEL_POLICY_CONFIG_PATH` | No | auto-detected | Path to policy configuration file (`config/policy/default.json` when present) |

### Electoral and deployment

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTINEL_ELECTORAL_PHASE` | No | `null` (from config) | Override electoral phase: `pre_campaign`, `campaign`, `silence_period`, `voting_day`, `results_period` |
| `SENTINEL_DEPLOYMENT_STAGE` | No | `supervised` | Override deployment stage: `shadow`, `advisory`, `supervised` |

### Rate limiting

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTINEL_RATE_LIMIT_PER_MINUTE` | No | `120` | Max requests per API key per minute |
| `SENTINEL_RATE_LIMIT_STORAGE_URI` | No | — | Rate limit storage URI (alternative to `SENTINEL_REDIS_URL`) |

### Redis hot triggers

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTINEL_REDIS_HOT_TRIGGER_KEY_PREFIX` | No | `sentinel:hot-triggers` | Redis key prefix for cached hot-trigger terms |
| `SENTINEL_REDIS_HOT_TRIGGER_TTL_SECONDS` | No | — | Optional TTL for hot-trigger cache keys |
| `SENTINEL_REDIS_SOCKET_TIMEOUT_SECONDS` | No | `0.05` | Redis socket timeout in seconds |

### OAuth (admin endpoints)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTINEL_OAUTH_TOKENS_JSON` | No | — | JSON object mapping static tokens to `{client_id, scopes}` |
| `SENTINEL_OAUTH_JWT_SECRET` | No | — | JWT signing secret. If set, enables JWT bearer auth instead of static tokens. |
| `SENTINEL_OAUTH_JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `SENTINEL_OAUTH_JWT_AUDIENCE` | No | — | Expected JWT audience claim (optional verification) |
| `SENTINEL_OAUTH_JWT_ISSUER` | No | — | Expected JWT issuer claim (optional verification) |

### ML and vector matching

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTINEL_VECTOR_MATCH_ENABLED` | No | `true` | Enable/disable vector similarity search |
| `SENTINEL_VECTOR_MATCH_THRESHOLD` | No | `0.82` | Minimum cosine similarity for vector matches |
| `SENTINEL_VECTOR_STATEMENT_TIMEOUT_MS` | No | `60` | Postgres statement timeout for vector queries |
| `SENTINEL_LID_MODEL_PATH` | No | — | Path to FastText language identification model |
| `SENTINEL_LID_CONFIDENCE_THRESHOLD` | No | `0.80` | Minimum confidence for language detection |
| `SENTINEL_EMBEDDING_PROVIDER` | No | `hash-bow-v1` | Embedding provider ID |
| `SENTINEL_CLASSIFIER_PROVIDER` | No | `none-v1` | Multi-label classifier provider ID |
| `SENTINEL_CLAIM_SCORER_PROVIDER` | No | `claim-heuristic-v1` | Claim scorer provider ID |

### Classifier shadow mode

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTINEL_CLASSIFIER_SHADOW_ENABLED` | No | `0` | Enable shadow classifier predictions (only in SHADOW/ADVISORY stages) |
| `SENTINEL_SHADOW_PREDICTIONS_PATH` | No | — | File path for shadow prediction logs |
| `SENTINEL_CLASSIFIER_TIMEOUT_MS` | No | `40` | Classifier timeout in milliseconds |
| `SENTINEL_CLASSIFIER_MIN_SCORE` | No | `0.55` | Minimum score to emit a shadow prediction |
| `SENTINEL_CLASSIFIER_CIRCUIT_FAILURE_THRESHOLD` | No | `3` | Consecutive failures before circuit breaker opens |
| `SENTINEL_CLASSIFIER_CIRCUIT_RESET_SECONDS` | No | `120` | Seconds before circuit breaker resets |

## Docker Compose setup (development/staging)

```bash
# Start Postgres + Redis
docker compose up -d --build postgres redis

# Run migrations
make apply-migrations

# Load seed lexicon
make seed-lexicon

# Start API
export SENTINEL_API_KEY='your-key'
make run
```

The included `docker-compose.yml` defines API, PostgreSQL 16 (pgvector), and Redis services. The command above starts only Postgres and Redis so you can run `make run` locally with hot reload.

## Production deployment guidance

For production:

- **Reverse proxy**: Place Sentinel behind nginx, Caddy, or a cloud load balancer. Terminate TLS at the proxy.
- **Managed database**: Use a managed PostgreSQL service with pgvector support. Ensure `pg_trgm` and `vector` extensions are available.
- **Replicas**: Sentinel is stateless (all state lives in Postgres/Redis). Run multiple API replicas behind a load balancer.
- **TLS**: All traffic between clients and the API should use HTTPS. Database connections should use SSL.
- **Admin endpoint isolation**: Consider running admin endpoints on a separate internal network or port, not exposed to the public internet.
- **Secrets**: Use a secrets manager for `SENTINEL_API_KEY`, `SENTINEL_DATABASE_URL`, and OAuth credentials. Do not pass secrets as command-line arguments.

## Database migrations

Sentinel includes 12 migration files in `migrations/`. Run them with:

```bash
make apply-migrations
```

Or directly:

```bash
python scripts/apply_migrations.py --database-url "$SENTINEL_DATABASE_URL"
```

| Migration | Description |
|-----------|-------------|
| `0001_lexicon_entries.sql` | Core lexicon entries table |
| `0002_lexicon_releases.sql` | Lexicon release lifecycle (draft/active/deprecated) |
| `0003_lexicon_release_audit.sql` | Audit trail for release state transitions |
| `0004_async_monitoring_core.sql` | Async monitoring queue tables |
| `0005_lexicon_release_audit_proposal_promote.sql` | Proposal promotion audit support |
| `0006_retention_legal_hold_primitives.sql` | Data retention and legal hold primitives |
| `0007_lexicon_entry_embeddings.sql` | pgvector embeddings for lexicon entries |
| `0008_appeals_core.sql` | Appeals state machine tables |
| `0009_appeals_original_decision_id_backfill.sql` | Backfill original decision IDs on appeals |
| `0010_monitoring_queue_event_uniqueness.sql` | Queue event deduplication |
| `0011_lexicon_entry_metadata_hardening.sql` | Metadata validation constraints |
| `0012_model_artifact_lifecycle.sql` | Model artifact version tracking |

Migrations are ordered and tracked via Alembic revision history. Running `make apply-migrations` repeatedly is safe.

## Lexicon lifecycle

The lexicon is Sentinel's primary enforcement mechanism. Terms are organized into versioned releases with a governed lifecycle.

### Release states

```
Draft  ──>  Active  ──>  Deprecated
```

Only one release can be active at a time (enforced by a database unique index). The active release is what the moderation endpoint uses.

### Seed lexicon

Sentinel ships with a 7-term demonstration seed (`data/lexicon_seed.json`):

| Term | Action | Label | Language |
|------|--------|-------|----------|
| kill | BLOCK | INCITEMENT_VIOLENCE | en |
| burn them | BLOCK | INCITEMENT_VIOLENCE | en |
| mchome | BLOCK | ETHNIC_CONTEMPT | sw |
| hunt you down | BLOCK | HARASSMENT_THREAT | en |
| deal with them | REVIEW | DOGWHISTLE_WATCH | en |
| wataona | REVIEW | DOGWHISTLE_WATCH | sw |
| rigged | REVIEW | DISINFO_RISK | en |

This seed is a **demonstration dataset only**. Production deployment requires building a comprehensive lexicon with domain-expert annotation covering the specific hate speech, incitement, and disinformation patterns relevant to your context.

### Lifecycle commands

```bash
# Load seed and activate (first-time setup)
make seed-lexicon

# Create a new release
make release-create VERSION=hatelex-v2.2

# Ingest terms into a draft release
make release-ingest VERSION=hatelex-v2.2 INPUT=data/lexicon_seed.json

# Validate a release against quality gates
make release-validate VERSION=hatelex-v2.2

# Activate a release (deactivates the previous active release)
make release-activate VERSION=hatelex-v2.2

# Deprecate an old release
make release-deprecate VERSION=hatelex-v2.1
```

## Electoral phase configuration

Sentinel adjusts moderation sensitivity based on the electoral cycle. Five phases are supported:

| Phase | Vector threshold | No-match action | Behavior |
|-------|-----------------|-----------------|----------|
| `pre_campaign` | 0.82 | ALLOW | Baseline sensitivity |
| `campaign` | 0.85 | ALLOW | Slightly tightened |
| `silence_period` | 0.88 | REVIEW | Unmatched content goes to review |
| `voting_day` | 0.90 | REVIEW | Maximum sensitivity |
| `results_period` | 0.88 | REVIEW | Maintained high sensitivity |

During `silence_period`, `voting_day`, and `results_period`, the `no_match_action` changes to `REVIEW`, meaning content that doesn't match any lexicon entry still gets flagged for human review.

### Setting the phase

Set the electoral phase via environment variable:

```bash
export SENTINEL_ELECTORAL_PHASE=campaign
```

Or in the policy config file (`config/policy/default.json`):

```json
{
  "electoral_phase": "campaign"
}
```

The environment variable takes precedence over the config file. If neither is set, no phase-specific overrides are applied.

### Phase safety constraint

Phase overrides cannot lower the BLOCK toxicity threshold below the baseline value. This prevents accidental weakening of the most critical moderation threshold during heightened periods.

## Deployment stages

Deployment stages control enforcement behavior. Use them to roll out Sentinel safely.

| Stage | BLOCK behavior | REVIEW behavior | ALLOW behavior | Use case |
|-------|---------------|-----------------|----------------|----------|
| `shadow` | Downgraded to ALLOW | Downgraded to ALLOW | No change | Observe decisions without enforcement; log-only mode |
| `advisory` | Downgraded to REVIEW | No change | No change | Enforcement active but no content is blocked; human review required for all blocks |
| `supervised` | Full enforcement | No change | No change | Production mode; all actions enforced as-is |

### Recommended rollout path

1. **SHADOW** — Deploy Sentinel and route traffic. Log all decisions but enforce nothing. Analyze decision quality.
2. **ADVISORY** — Enable enforcement but cap at REVIEW. Human moderators see what Sentinel would block. Build confidence.
3. **SUPERVISED** — Full enforcement. Sentinel blocks content autonomously based on lexicon matches.

Set the stage:

```bash
export SENTINEL_DEPLOYMENT_STAGE=advisory
```

Default is `supervised`. The policy version string encodes the active stage (e.g., `policy-2026.11@campaign#advisory`).

## OAuth setup for admin endpoints

Admin endpoints (appeals, transparency, release proposals, internal monitoring) require OAuth bearer token authentication.

### Option 1: Static token registry (simple)

Create a JSON file mapping tokens to client identities and scopes:

```json
{
  "token-abc-123": {
    "client_id": "admin-dashboard",
    "scopes": ["admin:appeal:read", "admin:appeal:write", "admin:transparency:read"]
  },
  "token-def-456": {
    "client_id": "ci-pipeline",
    "scopes": ["admin:proposal:read", "admin:proposal:review"]
  }
}
```

Set the environment variable:

```bash
export SENTINEL_OAUTH_TOKENS_JSON='{"token-abc-123": {"client_id": "admin-dashboard", "scopes": ["admin:appeal:read", "admin:appeal:write"]}}'
```

### Option 2: JWT bearer tokens

For production, configure JWT validation:

```bash
export SENTINEL_OAUTH_JWT_SECRET='your-jwt-signing-secret'
export SENTINEL_OAUTH_JWT_ALGORITHM='HS256'          # optional, default HS256
export SENTINEL_OAUTH_JWT_AUDIENCE='sentinel-admin'   # optional
export SENTINEL_OAUTH_JWT_ISSUER='your-auth-server'   # optional
```

JWTs must include `client_id` (or `sub`) and `scopes` (or `scope` as space-delimited string) claims.

### OAuth scopes

| Scope | Grants access to |
|-------|-----------------|
| `admin:appeal:read` | List appeals, reconstruct appeal audit trail |
| `admin:appeal:write` | Create appeals, transition appeal states |
| `admin:transparency:read` | Aggregate transparency reports |
| `admin:transparency:export` | Raw appeals data export |
| `admin:transparency:identifiers` | Include identifier fields (`request_id`, `original_decision_id`) in exports |
| `admin:proposal:read` | View release proposal permissions |
| `admin:proposal:review` | Submit, approve, reject, promote release proposals |
| `internal:queue:read` | Internal monitoring queue metrics |

## Monitoring

### Health check

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

### Metrics

```bash
# JSON format
curl http://localhost:8000/metrics

# Prometheus text format
curl http://localhost:8000/metrics/prometheus
```

The metrics endpoint returns action counts, HTTP status counts, latency histogram buckets, and validation error counts.

### Structured logging

Sentinel propagates `X-Request-ID` headers through all requests. If the client provides one, Sentinel uses it; otherwise one is generated. Use this ID to correlate logs across your infrastructure.

### Internal monitoring

With the `internal:queue:read` OAuth scope:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/internal/monitoring/queue/metrics
```

Returns queue depth and SLA breach snapshot data.

## Go-live readiness gate

Before production rollout, run the readiness gate:

```bash
python scripts/check_go_live_readiness.py --bundle-dir releases/go-live/<release-id>
```

This validates that all required artifacts (lexicon release, policy config, migration state, launch profile) are present and consistent. See `templates/go-live/` for the template bundle structure.
