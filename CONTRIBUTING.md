# Contributing to Sentinel

Thank you for contributing. This repository follows a spec-driven workflow: update specs first, then implementation.

## Contribution Flow

1. Open or link an issue with problem statement and scope.
2. Update relevant specs before code changes:
   - RFC: `docs/specs/rfcs/`
   - ADR: `docs/specs/adr/`
   - API/schema: `docs/specs/api/`, `docs/specs/schemas/`
3. Implement code and tests.
4. Update `docs/specs/tasks.md` status in the same PR.

## Local Setup

```bash
source .venv/bin/activate
make test
make contract
```

If working on DB-backed flows:

```bash
docker compose up -d --build
make apply-migrations
make seed-lexicon
make test-db
```

## Standards

- Python 3.12+, type hints for new/changed code.
- Keep moderation outputs deterministic and schema-aligned.
- Prefer small, focused PRs.
- Do not change public API behavior without spec updates.

## Required Checks Before PR

- `python -m pytest -q`
- `python scripts/check_contract.py`
- DB integration tests when relevant to migrations or release workflows.

## Pull Request Requirements

- Link issue/task IDs.
- List spec references (RFC/ADR/OpenAPI/schema).
- Describe behavior change and backward-compatibility impact.
- Include test evidence and migration notes (if any).

## Security

- Never commit secrets or production credentials.
- Use environment variables (`SENTINEL_API_KEY`, `SENTINEL_DATABASE_URL`).

## Governance and Conduct

- Follow `CODE_OF_CONDUCT.md` for all interactions.
- For moderation-outcome changes, review `docs/specs/governance.md`.
