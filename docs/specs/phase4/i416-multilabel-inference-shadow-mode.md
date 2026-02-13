# I-416: Multi-Label Inference Integration (Shadow-First)

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-13
- Scope: Introduce bounded-latency multi-label inference in shadow/advisory stages
- Task linkage: `I-416` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 5.2, Sec. 6.1, Sec. 13.1), `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`

## 1. Objective

Implement the first multi-label inference path while preserving deterministic governance and avoiding premature automated enforcement.

## 2. Required Behavior

1. Add classifier inference output mapping to existing label taxonomy.
2. Start in shadow mode with enforced decision unchanged by classifier output.
3. Emit observability for shadow-vs-enforced divergence.
4. Add explicit policy guardrail: classifier-only signal cannot directly `BLOCK` in initial rollout.
5. Persist shadow predictions for audit and promotion analysis:
   - `request_id`,
   - classifier model/version,
   - predicted labels/scores,
   - enforced action/labels,
   - timestamp.
6. Define classifier selection source:
   - selected model from `I-415` outputs or explicitly approved fallback classifier spec.
7. Define advisory-promotion criteria and minimum shadow window:
   - minimum 14 consecutive days of shadow metrics,
   - global weighted F1 >= baseline + 0.02 absolute,
   - per-language weighted F1 must not regress by > 0.03 absolute versus baseline,
   - benign political FP non-regression (<= +1pp),
   - shadow disagreement rate <= 15% over rolling 7-day window,
   - no unresolved critical safety regressions.
8. Runtime behavior on latency stress:
   - classifier timeout/error must fall back to deterministic path for that request,
   - sustained timeout/error triggers circuit-breaker disable for classifier path.

## 3. Acceptance Criteria

1. Shadow inference is configurable and disabled by default for enforcement.
2. Tests validate shadow outputs do not alter action when guardrail is active.
3. Metrics/logs include classifier latency and disagreement counters.
4. CI latency gate remains green with classifier path enabled in benchmark profile.
5. Promotion checklist and minimum shadow-duration evidence are documented.

## 4. Implementation Notes

1. Runtime classifier providers:
   - `src/sentinel_api/model_registry.py`
   - Added fallback classifier provider: `keyword-shadow-v1`
2. Guardrails and bounded latency:
   - `predict_classifier_shadow(...)` enforces timeout/error fallback and circuit-breaker disable on sustained failures.
3. Shadow observability and persistence:
   - `src/sentinel_api/main.py`
   - Stage-gated execution in `shadow|advisory` when `SENTINEL_CLASSIFIER_SHADOW_ENABLED=true`
   - Structured event: `classifier_shadow_prediction`
   - Optional JSONL persistence via `SENTINEL_SHADOW_PREDICTIONS_PATH`
4. Metrics:
   - `src/sentinel_api/metrics.py`
   - Added classifier shadow status counters, disagreement counter, and latency histogram (Prometheus).
5. Test coverage:
   - `tests/test_model_registry.py`
   - `tests/test_api.py`
   - `tests/test_metrics.py`
6. Promotion evidence checklist:
   - `docs/specs/benchmarks/i416-shadow-promotion-checklist.md`
