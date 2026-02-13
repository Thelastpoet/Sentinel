# RFC-0005: ML Readiness Execution Wave

- Status: Review
- Authors: Core maintainers
- Created: 2026-02-13
- Target milestone: Post-Phase-4 baseline hardening
- Related issues: TBD
- Supersedes: None

## 1. Summary

Define the next implementation wave that introduces model-ready interfaces and bounded-ML capabilities while preserving deterministic governance and public API contract stability.

## 2. Problem Statement

Current runtime is strong on governance and deterministic controls, but ML capability is limited: no multi-label classifier path, no production embedding model beyond hash-BOW baseline, and no explicit model runtime abstraction for safe model swapping.

## 3. Goals

- Add model integration interfaces without breaking existing behavior.
- Preserve `POST /v1/moderate` contract shape and reason-code auditability.
- Introduce multi-label inference in shadow-first mode with strict safety controls.
- Resolve embedding-model selection with measured latency/quality evidence.

## 4. Non-Goals

- Replacing deterministic policy logic with opaque end-to-end model decisions.
- Introducing automatic `BLOCK` decisions from uncalibrated model signals.
- Breaking API fields, schemas, or existing reason-code semantics.

## 5. Proposed Behavior

Delivery order (strict):

1. `I-413`: model runtime interfaces and registry wiring (embedding + classifier + claim detector adapters).
2. `I-414`: `model_version` semantics clarification and contract-safe documentation update.
3. `I-415`: embedding model bakeoff and selection gate versus `hash-bow-v1` baseline.
4. `I-416`: multi-label inference in shadow/advisory mode with bounded latency and safety guardrails.
5. `I-417`: claim-likeness calibration and governance thresholds using evaluation harness outputs.

## 6. API and Schema Impact

- Public API paths affected: none (shape-preserving).
- Response schema changes: none required for this wave.
- Backward compatibility: mandatory for all tasks.
- Documentation update: `model_version` meaning must be explicit in OpenAPI and RFC docs.

## 7. Policy and Reason Codes

- Existing reason-code families remain valid.
- Model signals are advisory unless explicitly promoted by approved policy updates.
- Multi-label model path must not directly `BLOCK` during initial rollout stages.

## 8. Architecture and Data Impact

- Components touched: `sentinel_core`, `sentinel_api/policy.py`, vector matcher adapter path, eval harness.
- Data impact: additive model metadata/config only.
- Migration requirements: optional/additive only.
- Hot-path latency budget remains P95 `<150ms`.

Indicative stage budgets during ML wave:

- Model adapter dispatch: <= 5ms
- Embedding inference/retrieval path: <= 60ms
- Multi-label inference path: <= 45ms
- Policy merge/decision assembly: <= 20ms

## 9. Security, Privacy, and Abuse Considerations

- Maintain existing authz and audit controls.
- Ensure model artifacts are versioned and provenance-traceable.
- Prevent model-only escalation to irreversible enforcement before calibration evidence is approved.

## 10. Alternatives Considered

1. Keep deterministic baseline only.
   - Rejected: leaves core ML readiness gaps unresolved.
2. Introduce full learned enforcement in one step.
   - Rejected: unacceptable safety and governance risk.

## 11. Rollout Plan

- Stage A: adapter interfaces + version semantics (`I-413`, `I-414`).
- Stage B: embedding model evaluation and decision (`I-415`).
- Stage C: classifier shadow/advisory rollout (`I-416`).
- Stage D: claim-likeness calibration governance closeout (`I-417`).

## 12. Acceptance Criteria

1. Tasks `I-413`..`I-417` land with explicit tests and no public contract break.
2. `scripts/check_contract.py`, `ruff`, `pyright`, and full test suite stay green.
3. Latency gate remains enforced in CI with artifact retention.
4. Safety policy guarantees are preserved (no uncalibrated model direct-block path).
5. All model artifacts and thresholds are auditable and versioned.

## 13. Test Plan

- Unit tests:
  - adapter interface behavior, fallback handling, version resolution,
  - classifier shadow decision isolation,
  - threshold-calibration logic.
- Integration tests:
  - moderation path with adapter-enabled model signals,
  - embedding selection benchmark harness integration.
- Contract tests:
  - schema/OpenAPI unchanged unless explicitly approved.
- Load/latency tests:
  - CI benchmark gate with model-enabled path enabled.

## 14. Observability

- Logs:
  - model adapter selected,
  - model artifact/version IDs,
  - shadow prediction vs enforced decision divergence.
- Metrics:
  - model latency histograms,
  - shadow disagreement rates,
  - per-language precision/recall deltas.
- Alerts:
  - sustained latency regression,
  - shadow disagreement spikes,
  - fallback-only mode persistence.

## 15. Open Questions

1. Which multilingual embedding model should be standard first (`e5`, `LaBSE`, other)?
2. What minimum shadow-quality threshold is required before advisory-mode promotion?
3. Should claim-likeness remain heuristic-backed after classifier rollout or become ensemble-weighted?
