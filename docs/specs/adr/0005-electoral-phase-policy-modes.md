# ADR-0005: Electoral-Phase Policy Modes

- Status: Accepted
- Date: 2026-02-12
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0001-v1-moderation-api.md`

## Context

`docs/master.md` requires election-phase policy posture across pre-campaign, campaign, silence period, voting day, and results period. Current runtime policy has no explicit phase mode model, which risks ad hoc behavior changes during high-risk periods.

## Decision

Adopt explicit electoral-phase policy modes as first-class runtime configuration.

Phase enum:

- `pre_campaign`
- `campaign`
- `silence_period`
- `voting_day`
- `results_period`

Configuration model:

- baseline policy remains required
- each phase may define additive overrides for thresholds, escalation defaults, and guardrails
- unknown phase values are invalid (startup/config validation failure)

Behavior rules:

1. If phase is explicitly configured, runtime uses that phase profile.
2. If phase is absent, runtime falls back to baseline profile.
3. Phase override may tighten enforcement; weakening high-severity protections requires explicit ADR/RFC update.
4. Every moderation response must include effective `policy_version`; internal logs must include effective phase.

## Rationale

- Prevent hidden policy drift during election-critical windows.
- Keep phase-specific behavior auditable and reproducible.
- Align runtime decisions with legal and governance commitments.

## Consequences

- Positive:
  - Deterministic election-period behavior.
  - Easier audits, appeals, and post-incident reconstruction.
- Negative:
  - More configuration and testing complexity.
- Neutral:
  - Baseline behavior remains valid when no phase override is active.

## Alternatives Considered

1. Keep one global policy profile year-round.
   - Rejected: inadequate control for election-risk windows.
2. Hardcode phase logic directly in application code.
   - Rejected: weak governance and poor auditability.

## Implementation Notes

- Required before 2027-03-31:
  - phase-aware policy schema
  - validation tests for every phase
  - observability fields for active phase
- Rollout safety:
  - canary deployment per phase profile
  - rollback path to baseline profile
  - documented operational playbook for phase switches
