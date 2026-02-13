# Quickstart

Choose your path:

- **Path A** — You're an integrator calling an existing Sentinel instance
- **Path B** — You're an operator setting up Sentinel from scratch

## Path A: Integrator

You have access to a running Sentinel instance and an API key. Four steps to your first moderation call.

### 1. Check health

```bash
curl -sS https://your-sentinel-host/health
```

Expected: `{"status":"ok"}`

### 2. Set your API key

```bash
export SENTINEL_API_KEY='your-api-key'
```

### 3. Send a moderation request

```bash
curl -sS -X POST https://your-sentinel-host/v1/moderate \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${SENTINEL_API_KEY}" \
  -d '{"text": "They should kill them now."}'
```

### 4. Read the response

```jsonc
{
  "toxicity": 0.92,
  "labels": ["INCITEMENT_VIOLENCE"],
  "action": "BLOCK",
  "reason_codes": ["R_INCITE_CALL_TO_HARM"],
  "evidence": [
    {
      "type": "lexicon",
      "match": "kill",
      "severity": 3,
      "lang": "en"
    }
  ],
  "language_spans": [{"start": 0, "end": 26, "lang": "en"}],
  "model_version": "sentinel-multi-v2",
  "lexicon_version": "hatelex-v2.1",
  "pack_versions": {"en": "pack-en-0.1", "sw": "pack-sw-0.1", "sh": "pack-sh-0.1"},
  "policy_version": "policy-2026.11",
  "latency_ms": 12
}
```

The `action` field is your enforcement decision. Map it in your application: `ALLOW` -> publish, `REVIEW` -> hold for moderator, `BLOCK` -> reject. See the [Integration Guide](integration-guide.md) for the full request/response schema and enforcement patterns.

---

## Path B: Operator

Set up a local Sentinel instance from source. You'll need Python 3.12+ and Docker with Docker Compose.

### 1. Clone and install

```bash
git clone https://github.com/Thelastpoet/sentinel.git
cd sentinel
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev,ops]
```

This installs the Sentinel API server and all development/operations tooling. The `.[ml]` extra is optional and only needed if you want to experiment with ML classifier scaffolding.

### 2. Start infrastructure

```bash
docker compose up -d --build postgres redis
```

This starts PostgreSQL (with pgvector) and Redis. Sentinel uses Postgres for lexicon storage, vector similarity search, appeals, and transparency exports. Redis is used for distributed rate limiting and hot-trigger caching.

### 3. Run database migrations

```bash
make apply-migrations
```

This runs all 12 migration files against the local Postgres instance, creating tables for lexicon entries, releases, embeddings, appeals, monitoring, and model artifacts.

### 4. Load the seed lexicon

```bash
make seed-lexicon
```

This loads the 7-term demonstration lexicon (`data/lexicon_seed.json`) and activates it. The seed contains example terms for `INCITEMENT_VIOLENCE`, `ETHNIC_CONTEMPT`, `HARASSMENT_THREAT`, `DOGWHISTLE_WATCH`, and `DISINFO_RISK`.

### 5. Start the API

```bash
export SENTINEL_API_KEY='replace-with-a-strong-key'
make run
```

The API starts on `http://localhost:8000` with hot reload enabled.

### 6. Verify

```bash
# Health check
curl -sS http://localhost:8000/health

# Moderation request
curl -sS -X POST http://localhost:8000/v1/moderate \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${SENTINEL_API_KEY}" \
  -d '{"text": "They should kill them now."}'
```

You should see a `BLOCK` response with label `INCITEMENT_VIOLENCE` and evidence pointing to the lexicon match on "kill".

### 7. Run tests (optional)

```bash
make test
make contract
```

## What success looks like

A successful moderation response always contains:

- `action` — the enforcement decision (`ALLOW`, `REVIEW`, or `BLOCK`)
- `labels` — what was detected (e.g., `INCITEMENT_VIOLENCE`)
- `reason_codes` — machine-readable codes explaining why (e.g., `R_INCITE_CALL_TO_HARM`)
- `evidence` — the specific matches that drove the decision
- Provenance fields (`model_version`, `lexicon_version`, `policy_version`, `pack_versions`) — for audit

## Seed lexicon caveat

The 7-term seed lexicon is a **demonstration dataset**. It covers basic examples across five labels but is not sufficient for production moderation. Production deployment requires building a comprehensive lexicon through domain-expert annotation. See the [Deployment Guide](deployment.md) for lexicon lifecycle management.

## Next steps

- **Integrators**: [Integration Guide](integration-guide.md) — full schema reference, enforcement patterns, error handling
- **Operators**: [Deployment Guide](deployment.md) — production setup, electoral phases, deployment stages
