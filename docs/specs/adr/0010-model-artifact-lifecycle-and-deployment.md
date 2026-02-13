# ADR-0010: Model Artifact Lifecycle and Deployment Governance

- Status: Proposed
- Date: 2026-02-13
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`

## Context

Lexicon and policy artifacts already have governance lifecycle controls, but model artifacts do not yet have equivalent controls for storage, activation, rollback, and provenance.

## Decision

Adopt a governed model artifact lifecycle with explicit states and deployment controls.

Lifecycle states:

1. `draft` (registered, not deployable)
2. `validated` (quality/safety/latency checks passed)
3. `active` (eligible for runtime selection)
4. `deprecated` (not selected for new rollout)
5. `revoked` (blocked from selection)

Minimum required metadata per artifact:

- `model_id`, `artifact_uri`, `sha256`, `created_at`, `created_by`,
- training/eval dataset references,
- metrics bundle reference,
- compatibility constraints (`python`, runtime backend, dimension/labels).

## Rationale

- Aligns model lifecycle rigor with existing lexicon release governance.
- Enables auditable rollout and rollback under election-period risk.
- Reduces operational ambiguity in incident response.

## Consequences

- Positive:
  - Traceable model provenance and safer production rollout.
  - Clear rollback path for degraded model behavior.
- Negative:
  - Additional operational overhead for artifact management.
- Neutral:
  - Public API shape remains unchanged.

## Alternatives Considered

1. Keep model files as ungoverned deployment assets.
   - Rejected: insufficient auditability and rollback rigor.
2. Reuse lexicon lifecycle tables directly.
   - Rejected: model artifact metadata and validation gates differ materially.

## Implementation Notes

- Tracked by `I-419` in `docs/specs/tasks.md`.
- Runtime selection must only allow `active` artifacts.
- Emergency rollback must support explicit previous-active model restore.
