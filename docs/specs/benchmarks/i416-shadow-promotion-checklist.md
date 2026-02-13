# I-416 Shadow Promotion Checklist

This checklist defines the minimum evidence required before promoting classifier output usage beyond shadow analysis.

## Minimum Shadow Window

- Duration: at least **14 consecutive days** of classifier shadow telemetry.
- Scope: production-equivalent traffic with `SENTINEL_CLASSIFIER_SHADOW_ENABLED=true` and deployment stage `shadow` or `advisory`.

## Promotion Gates

1. Global weighted F1 is `>= baseline + 0.02`.
2. Per-language weighted F1 does not regress by more than `0.03` absolute vs baseline.
3. Benign political false-positive rate does not regress by more than `+1pp`.
4. Rolling 7-day disagreement rate is `<= 15%`.
5. No unresolved critical safety regressions.
6. Timeout/error/circuit-open rates are within approved SLO bounds and do not degrade deterministic enforcement continuity.

## Required Artifacts

1. Shadow prediction logs (`classifier_shadow_prediction`) and sampled JSONL records.
2. Evaluation report from `scripts/evaluate_language_packs.py` with per-language and subgroup slices.
3. Latency evidence from `scripts/benchmark_hot_path.py` with classifier shadow path enabled.
4. Incident/safety review sign-off for any disagreement spikes or model fallback events.
