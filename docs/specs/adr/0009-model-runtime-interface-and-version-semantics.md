# ADR-0009: Model Runtime Interfaces and `model_version` Semantics

- Status: Proposed
- Date: 2026-02-13
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`

## Context

Sentinel currently uses deterministic policy logic with heuristic/vector support. ML capability expansion requires a stable integration boundary so model components can be introduced, swapped, and rolled back without policy-engine rewrites. In parallel, `model_version` is present in the public response contract and must remain audit-safe and non-misleading.

## Decision

1. Introduce protocol-based model runtime interfaces for:
   - embedding providers,
   - multi-label classifiers,
   - claim-likeness scorers.
2. Route model calls through registry/resolver components, not direct concrete imports in policy code.
3. Define `model_version` as the identifier for the active moderation inference artifact set (heuristic/model), not implicitly a learned model.
4. Require version/provenance metadata for all model adapters, including deterministic baselines.

## Rationale

- Keeps moderation policy deterministic while enabling incremental ML adoption.
- Reduces coupling and allows safe fallback between model and heuristic implementations.
- Preserves public contract continuity with clear semantics for integrators and auditors.

## Consequences

- Positive:
  - Cleaner extension path for future models.
  - Safer rollout/rollback and clearer audit trails.
  - Lower risk of contract ambiguity around `model_version`.
- Negative:
  - Added adapter/registry complexity.
  - Additional test and observability burden.
- Neutral:
  - Public API shape remains unchanged.

## Alternatives Considered

1. Keep direct concrete model calls in policy engine.
   - Rejected: increases coupling and rollback risk.
2. Rename `model_version` field immediately.
   - Rejected: would be contract-breaking; documentation clarification is safer.

## Implementation Notes

- Tracked by `I-413` and `I-414` in `docs/specs/tasks.md`.
- All adapter additions must include:
  - deterministic fallback behavior,
  - latency budget measurement,
  - explicit reason-code/policy interaction tests.
