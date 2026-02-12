# ADR-0002: Lexicon Release Lifecycle Governance

- Status: Accepted
- Date: 2026-02-12
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0001-v1-moderation-api.md`

## Context

Lexicon entries are versioned, but without explicit release lifecycle states the runtime cannot deterministically select the intended version during updates.

## Decision

Introduce `lexicon_releases` with explicit statuses:

- `draft`
- `active`
- `deprecated`

Runtime behavior:

- Postgres loader reads entries only for the single `active` release.
- If Postgres cannot provide an active release snapshot, runtime falls back to file seed backend.

Operational behavior:

- `scripts/manage_lexicon_release.py` handles create, activate, deprecate, and list operations.
- `scripts/manage_lexicon_release.py ingest` loads validated entries into draft releases only.
- `scripts/manage_lexicon_release.py validate` blocks unsafe activation candidates (for example, versions with zero active entries).
- `scripts/sync_lexicon_seed.py` ensures release creation and optional initial activation.

## Rationale

- Prevents ambiguous multi-version reads.
- Enables controlled rollouts and rollbacks through release state changes.
- Keeps activation semantics auditable and explicit.

## Consequences

- Positive:
  - Deterministic version selection in production.
  - Safer governance during high-risk election periods.
- Negative:
  - Additional operational step for activating new releases.
  - Requires migration and tooling updates.
- Neutral:
  - File fallback path remains unchanged for local development resilience.

## Alternatives Considered

1. Always choose lexicographically latest `lexicon_version`.
   - Rejected because it bypasses governance and can activate unintended data.
2. Keep multiple versions active simultaneously.
   - Rejected due to nondeterministic moderation outcomes.

## Implementation Notes

- DB migration: `migrations/0002_lexicon_releases.sql`
- Runtime query change: `src/sentinel_api/lexicon_repository.py`
- Operational tooling:
  - `scripts/manage_lexicon_release.py`
  - `scripts/sync_lexicon_seed.py`
