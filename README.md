# Sentinel

Sentinel is a multilingual moderation API for election-risk and civic discourse safety.
It is designed for products that need deterministic moderation decisions with audit evidence, especially in code-switched East African contexts.

## Who this is for

- Community forums
- News platforms
- Civil society reporting tools
- Fact-check and trust-and-safety teams

## What Sentinel returns

For each text input, Sentinel returns:

- `action`: `ALLOW`, `REVIEW`, or `BLOCK`
- `labels` and `reason_codes`
- `evidence` used for the decision
- provenance fields (`model_version`, `lexicon_version`, `policy_version`)

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev,ops]

# optional ML extras
python -m pip install -e .[ml]

docker compose up -d --build
export SENTINEL_API_KEY='replace-with-strong-key'
python scripts/apply_migrations.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel
python scripts/sync_lexicon_seed.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel --activate-if-none
uvicorn sentinel_api.main:app --host 0.0.0.0 --port 8000
```

Test a request:

```bash
curl -sS -X POST http://localhost:8000/v1/moderate \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${SENTINEL_API_KEY}" \
  -d '{"text":"They should kill them now."}'
```

## Integration model

Your backend calls Sentinel before publish:

1. Send user text to `POST /v1/moderate`
2. Apply action:
   - `ALLOW` -> publish
   - `REVIEW` -> moderation queue
   - `BLOCK` -> reject
3. Store decision metadata for audit and appeals

## Documentation

- [Docs index](docs/README.md)
- [Quickstart](docs/quickstart.md)
- [Integration Guide](docs/integration-guide.md)
- [Deployment Guide](docs/deployment.md)
- [API Reference](docs/api-reference.md)
- [Security Notes](docs/security.md)
- [FAQ](docs/faq.md)

## License

Apache-2.0. See [LICENSE](LICENSE).
