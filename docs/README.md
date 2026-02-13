# Sentinel Documentation

Sentinel is an open-source moderation API for election safety, currently supporting English (`en`), Swahili (`sw`), and Sheng (`sh`). These docs cover integration, deployment, and operation.

## Interface stability levels

- **Public integration contract (stable)**: `/v1/moderate` plus `contracts/api/openapi.yaml` and top-level request/response schemas.
- **Operator/admin interfaces (managed, may evolve)**: `/admin/*` and `/internal/*` endpoints used for operations and governance workflows.
- **Internal schemas (implementation contracts)**: `contracts/schemas/internal/*` support tests and operational pipelines; they are not a promise of long-term external API stability.

## Reading paths

### Platform integrators

You want to call the Sentinel API from your application.

1. [Quickstart](quickstart.md) — Path A: send your first moderation request
2. [Integration Guide](integration-guide.md) — Authentication, request/response schemas, enforcement patterns, error handling
3. [API Reference](api-reference.md) — Public and moderation endpoints

### Self-host operators

You want to deploy and manage a Sentinel instance.

1. [Quickstart](quickstart.md) — Path B: stand up a local instance
2. [Deployment Guide](deployment.md) — Infrastructure, configuration, migrations, lexicon lifecycle, electoral phases
3. [Security](security.md) — Authentication, authorization, safety architecture
4. [API Reference](api-reference.md) — Admin and internal endpoints

## Document index

| Document | Audience | Description |
|----------|----------|-------------|
| [Quickstart](quickstart.md) | Both | Two paths: integrator (4 steps) and operator (full local setup) |
| [Integration Guide](integration-guide.md) | Integrators | Complete request/response reference, enforcement mapping, rate limiting, errors |
| [Deployment Guide](deployment.md) | Operators | Architecture, env vars, Docker, migrations, lexicon, phases, stages, OAuth, monitoring |
| [API Reference](api-reference.md) | Both | All 13 endpoints: public, moderation, admin appeals, transparency, release proposals |
| [Security](security.md) | Operators | Auth, scopes, input validation, safety constraints, data handling |
| [FAQ](faq.md) | Both | Common questions split by audience |

## Related resources

| Path | Contents |
|------|----------|
| `contracts/api/openapi.yaml` | Machine-readable contract for `/health`, `/metrics`, and `/v1/moderate` |
| `contracts/schemas/` | JSON Schema definitions (public + internal operator schemas) |
| `templates/go-live/` | Go-live readiness gate template bundle |
| `config/policy/default.json` | Default policy configuration (thresholds, phases, hints) |
| `data/lexicon_seed.json` | 7-term demonstration seed lexicon |
| `migrations/` | Database migration files (0001-0012) |
