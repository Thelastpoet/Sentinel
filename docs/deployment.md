# Deployment Guide

## Runtime components

- Sentinel API (FastAPI)
- PostgreSQL (required for governed lifecycle features)
- Redis (hot trigger caching)

## Required environment variables

- `SENTINEL_API_KEY`
- `SENTINEL_DATABASE_URL`

Common optional variables:

- `SENTINEL_REDIS_URL`
- `SENTINEL_POLICY_CONFIG_PATH`
- `SENTINEL_ELECTORAL_PHASE`
- `SENTINEL_DEPLOYMENT_STAGE`

## Docker Compose deployment

```bash
docker compose up -d --build
python scripts/apply_migrations.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel
python scripts/sync_lexicon_seed.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel --activate-if-none
```

## Readiness checks

```bash
curl -sS http://localhost:8000/health; echo
curl -sS http://localhost:8000/metrics; echo
```

## Go-live governance gate

Release approval is enforced with:

```bash
python scripts/check_go_live_readiness.py --bundle-dir releases/go-live/<release-id>
```
