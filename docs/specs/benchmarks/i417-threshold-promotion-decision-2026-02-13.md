# I-417 Claim-Likeness Threshold Promotion Decision

- Decision date: 2026-02-13
- Source report: `docs/specs/benchmarks/i417-claim-likeness-calibration-2026-02-13.json`
- Dataset release: `data/datasets/ml_calibration/v1/release_metadata.json`
- Annotation guide: `docs/specs/annotation-guides/ml-calibration-v1.md`

## Threshold Promotion

- Previous baseline: `medium=0.40`, `high=0.70`
- Promoted thresholds: `medium=0.45`, `high=0.75`
- Active policy version: `policy-2026.11`

## Safety Impact Summary

- Global F1: no regression (`0.400 -> 0.400`)
- Benign political FP rate: no regression (`0.666667 -> 0.666667`)
- Per-language F1 non-regression gate: satisfied for Tier-1 languages in calibration report.

## Governance Sign-Off

- Maintainer reviewer: pending
- Policy/governance reviewer: pending
- Notes: Promotion is deterministic and contract-safe; no public API shape change.
