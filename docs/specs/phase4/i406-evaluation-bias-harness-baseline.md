# I-406: Per-Language Evaluation and Bias-Audit Harness (Baseline)

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Baseline evaluation harness for language-level quality and bias metrics
- Task linkage: `I-406` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 13.2, Sec. 19), `docs/specs/phase4/i401-tier2-language-priority-and-gates.md`

## 1. Objective

Provide a deterministic evaluation pipeline that reports:

- precision, recall, and F1 by language and harm class;
- benign political false-positive rates;
- subgroup disparity ratios for benign false positives.

This baseline is the required measurement foundation for `I-405` stage gates and `I-407` Tier-2 language-pack releases.

## 2. Input Contract (JSONL)

One JSON object per line:

```json
{
  "id": "sample-001",
  "text": "Example content",
  "language": "en",
  "labels": ["BENIGN_POLITICAL_SPEECH"],
  "is_benign_political": true,
  "subgroup": "group-a"
}
```

Rules:

- `id`, `text`, `language`, `labels` are required.
- `labels` must use the canonical taxonomy labels.
- `is_benign_political` defaults to `true` when label set includes `BENIGN_POLITICAL_SPEECH`.
- `subgroup` is optional and used for disparity tracking.

## 3. Baseline Outputs

The harness must emit JSON containing:

- `global_harm_label_metrics`: per-label `tp/fp/fn/precision/recall/f1`.
- `language_harm_label_metrics`: same metrics partitioned by language.
- `benign_false_positive_metrics`:
  - `block_fp_rate`
  - `block_or_review_fp_rate`
- `subgroup_disparity_metrics`:
  - per-subgroup benign false-positive rates
  - max disparity ratio vs global benign `block_or_review_fp_rate`.

## 4. Baseline Implementation Surface

- Core metrics logic: `src/sentinel_core/eval_harness.py`
- CLI entrypoint: `scripts/evaluate_language_packs.py`
- Baseline tests: `tests/test_eval_harness.py`

## 5. Acceptance Criteria (I-406 Baseline)

1. Harness loads JSONL datasets with strict validation and deterministic parsing.
2. Harness computes precision/recall/F1 by harm class globally and per language.
3. Harness computes benign false-positive rates and subgroup disparity metrics.
4. CLI produces machine-readable JSON report and optional file output.
5. Tests cover parsing failures, metric math, and disparity ratio behavior.

## 6. Out of Scope for Baseline

- External dashboarding and UI.
- Automated data ingestion from partner connectors.
- Statistical confidence intervals and significance testing.
- Production alerting rules (added in later Phase 4 tasks).
