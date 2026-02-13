# Security

This document covers Sentinel's security architecture: authentication, authorization, input validation, safety constraints, and data handling. It is primarily for operators deploying Sentinel in production.

## Authentication

### API key (moderation endpoint)

The `POST /v1/moderate` endpoint requires an `X-API-Key` header. The key is compared with constant-time `compare_digest` logic to reduce timing-attack risk.

- Set a strong, random API key via `SENTINEL_API_KEY`
- Never expose the key to frontend clients — Sentinel should only be called server-to-server
- Rotate the key by updating the environment variable and restarting the API

### OAuth bearer tokens (admin endpoints)

All admin and internal endpoints require an `Authorization: Bearer <token>` header. Sentinel supports two authentication backends:

**Static token registry** — For development and simple deployments. Configure via `SENTINEL_OAUTH_TOKENS_JSON` with a JSON mapping of tokens to client identities and scopes.

**JWT bearer tokens** — For production. Configure via `SENTINEL_OAUTH_JWT_SECRET`. Supports audience and issuer verification via `SENTINEL_OAUTH_JWT_AUDIENCE` and `SENTINEL_OAUTH_JWT_ISSUER`. JWTs must include `client_id` (or `sub`) and `scopes` (or `scope` as space-delimited string) claims.

If neither is configured, admin endpoints return 401 for all requests.

## Authorization (OAuth scopes)

Each admin endpoint requires a specific OAuth scope. Requests without the required scope receive 403 Forbidden.

| Scope | Endpoints |
|-------|-----------|
| `admin:appeal:read` | List appeals, reconstruct audit trail |
| `admin:appeal:write` | Create appeals, transition appeal states |
| `admin:transparency:read` | Aggregate transparency reports |
| `admin:transparency:export` | Raw appeals data export |
| `admin:transparency:identifiers` | Include PII fields in exports (additive — also requires `admin:transparency:export`) |
| `admin:proposal:read` | View release proposal permissions |
| `admin:proposal:review` | Submit, approve, reject, promote release proposals |
| `internal:queue:read` | Internal monitoring queue metrics |

Follow the principle of least privilege: grant each client only the scopes it needs.

## Input validation

Sentinel uses Pydantic v2 models with `extra="forbid"`:

- **Text length**: 1-5000 characters (rejects empty strings and oversized input)
- **Context fields**: `source` (max 100), `locale` (max 20), `channel` (max 50)
- **Request ID**: Max 128 characters
- **Extra fields rejected**: Any field not in the schema causes a 400 error
- **Reason code format**: Enforced pattern `R_[A-Z0-9_]+`

Validation failures return structured `ErrorResponse` payloads with `error_code: "HTTP_400"`.

## Rate limiting

Per-key sliding window rate limiting (default: 120 requests/minute):

- In-memory by default; distributed via Redis when `SENTINEL_REDIS_URL` or `SENTINEL_RATE_LIMIT_STORAGE_URI` is set
- Falls back to in-memory rate limiting if Redis is unavailable
- Returns `429 Too Many Requests` with `Retry-After` header when exceeded

## Safety architecture

Sentinel's moderation pipeline includes several intentional safety constraints that prevent the system from causing harm even if misconfigured.

### Deployment stages as safety control

Deployment stages gate what enforcement actions Sentinel can take:

| Stage | Effect |
|-------|--------|
| `SHADOW` | All decisions downgraded to ALLOW. Sentinel logs what it *would* do but enforces nothing. |
| `ADVISORY` | BLOCK decisions downgraded to REVIEW. No content is auto-blocked. |
| `SUPERVISED` | Full enforcement. This is the only stage where BLOCK is applied. |

New deployments should start in SHADOW, progress to ADVISORY after validating decision quality, and only move to SUPERVISED with confidence in the lexicon and policy configuration.

### Electoral phases as safety control

Electoral phases automatically tighten sensitivity thresholds as election day approaches:

- During `SILENCE_PERIOD`, `VOTING_DAY`, and `RESULTS_PERIOD`, unmatched content defaults to REVIEW instead of ALLOW
- Phase overrides **cannot lower** the BLOCK toxicity threshold below baseline — this is enforced in code to prevent accidental weakening of the most critical safety gate
- Vector match thresholds increase (0.82 -> 0.90) to reduce false positives during high-stakes periods

### Vector match cannot BLOCK

This is a hard safety constraint: vector similarity matches can only produce REVIEW, never BLOCK. Only deterministic lexicon matches (exact normalized regex) can block content. This ensures that no fuzzy/probabilistic matching can autonomously suppress speech.

### Model-derived paths are safety-capped

The multi-label classifier runs in shadow mode and does not affect enforcement actions. Claim-likeness scoring can flag content to `REVIEW`, but it cannot produce `BLOCK`. The deterministic lexicon path remains the only direct path to `BLOCK`.

## Data handling

### Transparency exports and identifier masking

The transparency export endpoint (`GET /admin/transparency/exports/appeals`) masks PII fields (`request_id`, `original_decision_id`) by default. Including these fields requires both the `admin:transparency:export` scope and the additional `admin:transparency:identifiers` scope. This two-scope design prevents accidental PII exposure in public transparency reports.

### Legal hold primitives

Database migration `0006_retention_legal_hold_primitives.sql` adds data retention and legal hold capabilities. These primitives support compliance with data retention requirements and legal proceedings.

### Audit trail

Every moderation response includes full provenance (model version, lexicon version, policy version, pack versions). The appeals system reconstructs the complete decision context at the time of the original moderation call, enabling fair review even after artifacts have been updated.

## Secrets management

- **Never pass secrets as command-line arguments** (they appear in process listings)
- Use environment variables or a secrets manager for `SENTINEL_API_KEY`, `SENTINEL_DATABASE_URL`, `SENTINEL_OAUTH_JWT_SECRET`, and `SENTINEL_OAUTH_TOKENS_JSON`
- The API key is compared using constant-time comparison to prevent timing side channels
- Database connection strings should use SSL in production

## Network security

- **TLS**: Terminate TLS at a reverse proxy (nginx, Caddy, cloud load balancer). All client-to-API traffic should use HTTPS.
- **Admin endpoint isolation**: Admin endpoints (`/admin/*`, `/internal/*`) should not be exposed to the public internet. Use network-level access controls or run admin endpoints on a separate port/service.
- **Database**: Use SSL for Postgres connections. Restrict database access to the API server's network.
- **Redis**: If using Redis for distributed rate limiting, ensure the Redis instance is not publicly accessible.
