# Quickstart

This quickstart gets Sentinel running locally and validates one moderation request.

## Prerequisites

- Python 3.12+
- Docker + Docker Compose

## 1. Install and activate

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev,ops]
```

Optional ML dependencies:

```bash
python -m pip install -e .[ml]
```

## 2. Start infrastructure

```bash
docker compose up -d --build
```

## 3. Configure and seed

```bash
export SENTINEL_API_KEY='replace-with-strong-key'
python scripts/apply_migrations.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel
python scripts/sync_lexicon_seed.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel --activate-if-none
```

## 4. Run API

```bash
uvicorn sentinel_api.main:app --host 0.0.0.0 --port 8000
```

## 5. Verify health and moderation

```bash
curl -sS http://localhost:8000/health; echo
curl -sS -X POST http://localhost:8000/v1/moderate \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${SENTINEL_API_KEY}" \
  -d '{"text":"They should kill them now."}'; echo
```

## 6. Validate installation

```bash
python -m pytest -q
python scripts/check_contract.py
```
