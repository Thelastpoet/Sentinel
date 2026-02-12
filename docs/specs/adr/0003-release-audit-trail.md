# ADR-0003: Lexicon Release Audit Trail

- Status: Accepted
- Date: 2026-02-12
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0001-v1-moderation-api.md`

## Context

Release governance actions affect moderation behavior and require accountability across election-sensitive periods.

## Decision

Add a database-backed audit trail for release operations.

- New table: `lexicon_release_audit`
- Logged actions: `create`, `ingest`, `activate`, `deprecate`, `validate`
- Audit record fields: `release_version`, `action`, `actor`, `details`, `created_at`

## Rationale

- Enables post-incident reconstruction of operational decisions.
- Supports compliance and oversight workflows.
- Keeps rollout activity observable without relying on application logs only.

## Consequences

- Positive:
  - Clear traceability for release lifecycle decisions.
  - Easier debugging of unexpected policy behavior shifts.
- Negative:
  - Additional schema and operational maintenance.
- Neutral:
  - API contract remains unchanged.

## Alternatives Considered

1. Log-only auditing in application output.
   - Rejected: not durable enough for governance-grade traceability.
2. No explicit audit trail.
   - Rejected: insufficient for safety-critical moderation operations.

## Implementation Notes

- Migration: `migrations/0003_lexicon_release_audit.sql`
- Init schema mirror: `infra/postgres-init.sql`
- Tooling: `scripts/manage_lexicon_release.py` (`--actor`, `audit` command)
