# ADR-0001: Lexicon Repository With Postgres-First Fallback

- Status: Accepted
- Date: 2026-02-12
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0001-v1-moderation-api.md`

## Context

Sentinel needs a production-ready lexicon source while remaining easy to run for open-source contributors without infrastructure.

## Decision

Use a repository abstraction for lexicon loading:

- `PostgresLexiconRepository` as the primary backend when `SENTINEL_DATABASE_URL` is set.
- `FileLexiconRepository` for local seed data (`data/lexicon_seed.json`).
- `FallbackLexiconRepository` to gracefully fall back to file data if Postgres is unavailable or empty.

## Rationale

- Keeps policy and API layers independent of storage implementation.
- Enables reliable local development without mandatory external services.
- Supports production posture while preserving deterministic behavior under dependency failures.

## Consequences

- Positive:
  - Clear extension point for future Redis/cache-backed repositories.
  - Safer startup behavior in degraded environments.
- Negative:
  - Slightly more indirection than direct file/DB reads.
  - Requires tests across both repository and integration layers.
- Neutral:
  - Existing moderation behavior remains unchanged.

## Alternatives Considered

1. Direct DB reads from policy layer.
   - Rejected due to coupling and reduced testability.
2. File-only backend.
   - Rejected because it cannot support operational update workflows.

## Implementation Notes

- Repository abstraction is implemented in `src/sentinel_api/lexicon_repository.py`.
- Runtime assembly is configured in `src/sentinel_api/lexicon.py`.
- DB schema remains in `migrations/0001_lexicon_entries.sql`.
