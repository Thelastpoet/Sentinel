# Sentinel

**Multilingual political-safety infrastructure for the 2027 Kenyan General Election.**

Sentinel detects ethnic incitement, hate speech, and election-related disinformation across Kenya's multilingual digital landscape — where Swahili, Sheng, English, Luhya, Kikuyu, Luo, Kalenjin, and other languages mix freely in a single post.

Built for newsrooms, digital publishers, civil society platforms, and fact-check partners who need fast, auditable moderation decisions during high-stakes election cycles.

## Why Sentinel?

Generic moderation tools fail on Kenyan political content. Harmful rhetoric appears in code-switched text, local slang, and coded dog whistles that shift meaning by region, language, and electoral phase. Sentinel is purpose-built for this reality:

- **Code-switching first** — language identification at the span level, not the post level.
- **Deterministic decisions** — every ALLOW, REVIEW, or BLOCK comes with reason codes, evidence traces, and artifact versions. No black boxes.
- **Election-aware policy** — moderation posture adapts automatically across campaign, silence, voting, and results periods.
- **Human-in-the-loop by design** — ambiguity escalates to reviewers. Humans remain accountable.
- **Governed and auditable** — versioned lexicons, appeals workflows, transparency exports, and tamper-evident audit trails.

## How it works

```
Input text
  -> Normalize and route language spans (sw, en, sheng, kik, Luh, luo, kal)
  -> Fast lexical triggers (Redis, O(1) lookup)
  -> Semantic similarity (Postgres + pgvector)
  -> Deterministic policy logic
  -> Action: ALLOW / REVIEW / BLOCK
  -> Structured output (labels, evidence, reason codes, versions, latency)
```

Every response follows a strict contract:

```json
{
  "toxicity": 0.87,
  "labels": ["INCITEMENT_VIOLENCE", "ETHNIC_CONTEMPT"],
  "action": "BLOCK",
  "reason_codes": ["R_INCITE_CALL_TO_HARM", "R_ETHNIC_SLUR_MATCH"],
  "evidence": [
    {"type": "lexicon", "match": "****", "severity": 3, "lang": "sw"},
    {"type": "vector_match", "match_id": "lex_10293", "similarity": 0.89}
  ],
  "language_spans": [
    {"start": 0, "end": 12, "lang": "sw"},
    {"start": 13, "end": 40, "lang": "kik"}
  ],
  "model_version": "sentinel-multi-v2",
  "lexicon_version": "hatelex-v2.1",
  "policy_version": "policy-2026.10",
  "latency_ms": 94
}
```

## Features

| Capability | Description |
|---|---|
| Real-time Moderation API | `/v1/moderate` endpoint with P95 < 150ms target |
| Multilingual language routing | Span-level detection for Tier-1 and Tier-2 Kenyan languages |
| Hate-Lex knowledge base | Versioned lexicon of slurs, dog whistles, violence idioms, and disinfo templates |
| Async monitoring pipeline | Ingests partner signals, clusters emerging threats, generates governed update proposals |
| Electoral phase modes | Policy posture shifts across pre-campaign, campaign, silence, voting day, and results period |
| Deployment stages | Graduated rollout: shadow -> advisory -> supervised |
| Appeals and transparency | Full case reconstruction, state-machine appeals, and privacy-controlled transparency exports |
| Partner connectors | Fact-check integrations with retry, backoff, and circuit breaker resilience |

## Project status

**Active development** — core implementation phases are complete through I-407. Final go-live hardening (I-408 through I-412) is in progress. See the [task board](docs/specs/tasks.md) for current status.

Not yet in production. Contributions and feedback are welcome.

## Getting started

### Prerequisites

- Python 3.12+
- Docker and Docker Compose (for full stack with Postgres and Redis)

### Quick start with Docker Compose

```bash
git clone https://github.com/Thelastpoet/sentinel.git
cd sentinel

# Set a strong API key (do not use the default in production)
export SENTINEL_API_KEY='your-strong-api-key-here'

docker compose up --build
make apply-migrations
make seed-lexicon
```

Verify the service is running:

```bash
curl -sS http://localhost:8000/health
# {"status":"ok"}
```

### Local development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev,ops]

export SENTINEL_API_KEY='your-strong-api-key-here'
uvicorn sentinel_api.main:app --reload
```

### Try a moderation request

```bash
curl -sS -X POST http://localhost:8000/v1/moderate \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${SENTINEL_API_KEY}" \
  -d '{"text":"They should kill them now."}'
```

## Running tests

```bash
# Unit tests
python -m pytest -q

# Contract validation
python scripts/check_contract.py

# Hot-path latency benchmark
python scripts/benchmark_hot_path.py --iterations 300 --warmup 30 --p95-budget-ms 150

# Tier-2 language pack verification
python scripts/verify_tier2_wave1.py --registry-path data/langpacks/registry.json --pretty
```

### Pre-commit hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Repository layout

```
src/
  sentinel_core/       shared models, state machines, policy config
  sentinel_router/     span-level language identification
  sentinel_lexicon/    lexicon matching, hot triggers, vector search
  sentinel_langpack/   language pack registry and normalization
  sentinel_api/        FastAPI application, auth, workers, admin endpoints
scripts/               operational and verification tooling
config/                policy configuration files
data/                  lexicon seeds, eval sets, language-pack artifacts
migrations/            Postgres schema migrations (Alembic)
infra/                 database init scripts
docs/                  master plan, specs, governance, operations
tests/                 unit and integration tests
```

## Architecture and specs

Sentinel follows a **spec-first workflow**: specs are written and approved before implementation.

| Document | Purpose |
|---|---|
| [Master plan](docs/master.md) | Product direction and system blueprint |
| [Task board](docs/specs/tasks.md) | Implementation progress tracker |
| [OpenAPI spec](docs/specs/api/openapi.yaml) | Public API contract |
| [JSON schemas](docs/specs/schemas/) | Request/response payload schemas |
| [RFCs](docs/specs/rfcs/) | Feature-level behavioral specifications |
| [ADRs](docs/specs/adr/) | Architecture decision records |

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| API framework | FastAPI |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Packaging | uv workspace |
| Testing | pytest |
| Container runtime | Docker Compose (dev), Kubernetes (production target) |

## Contributing

Contributions are welcome, especially for:

- **Language packs** — normalization rules, lexicon entries, and evaluation sets for Kenyan languages
- **Lexicon proposals** — new terms, dog whistles, or coded rhetoric patterns
- **Bug reports and fixes** — especially around false positives on legitimate political speech
- **Documentation** — translations, onboarding guides, and operational runbooks

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request. All interactions are governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

For changes that affect moderation outcomes, review the [governance spec](docs/specs/governance.md). These require at least two maintainer approvals.

## Security

This project handles election-safety workflows. Deployments, credentials, and incident procedures should be treated as high-risk operational assets.

- **Never commit secrets or production credentials.** Use environment variables.
- **Follow staged rollout controls** documented in the [go-live readiness gate](docs/specs/phase4/i408-go-live-readiness-gate.md).
- **Report security vulnerabilities** responsibly by emailing the maintainers directly. Do not open public issues for security bugs.

## License

Apache-2.0. See [LICENSE](LICENSE) for details.
