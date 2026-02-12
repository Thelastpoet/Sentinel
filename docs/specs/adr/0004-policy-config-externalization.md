# ADR-0004: Externalized Policy Configuration

- Status: Accepted
- Date: 2026-02-12
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0001-v1-moderation-api.md`

## Context

Policy behavior was partially hardcoded in runtime code, making controlled policy updates harder to audit and roll out.

## Decision

Move runtime policy constants into a versioned JSON config:

- default path: `config/policy/default.json`
- optional override: `SENTINEL_POLICY_CONFIG_PATH`
- validated at load time with a strict schema

Externalized fields include:

- `version`
- `model_version`
- `pack_versions`
- `toxicity_by_action`
- allow-path defaults (label/reason/confidence)
- language hint lists

## Rationale

- Enables controlled policy updates without code edits.
- Keeps policy versioning explicit and auditable.
- Reduces risk of hidden drift between code and policy intent.

## Consequences

- Positive:
  - Better governance and rollout control.
  - Easier experimentation with policy tuning.
- Negative:
  - Misconfigured files can break startup unless validated.
- Neutral:
  - API response contract remains unchanged.

## Alternatives Considered

1. Keep constants in code.
   - Rejected: weak governance and slower policy iteration.
2. Store policy in database only.
   - Deferred: adds operational complexity for the current phase.

## Implementation Notes

- Runtime loader: `src/sentinel_api/policy_config.py`
- Runtime usage: `src/sentinel_api/policy.py`
- Default config: `config/policy/default.json`
