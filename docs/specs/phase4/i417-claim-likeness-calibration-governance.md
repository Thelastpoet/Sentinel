# I-417: Claim-Likeness Calibration and Governance Thresholds

## 0. Document Control

- Status: Ratified for implementation
- Effective date: 2026-02-13
- Scope: Calibrate claim-likeness thresholds with labeled data and governance sign-off
- Task linkage: `I-417` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 9.1, Sec. 13.2, Sec. 21.2), `docs/specs/phase4/i412-disinfo-claim-likeness-baseline.md`, `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`

## 1. Objective

Move claim-likeness from static baseline thresholds to evidence-backed calibrated thresholds per governance process.

## 2. Required Behavior

1. Define calibration dataset and methodology.
2. Evaluate false-positive/false-negative tradeoffs by language/subgroup.
3. Propose threshold updates with explicit safety impact analysis.
4. Require governance sign-off before promoting new thresholds.

## 3. Acceptance Criteria

1. Calibration report includes per-language and subgroup metrics.
2. Threshold changes are versioned in policy config and auditable.
3. Regression tests verify deterministic score-to-band mapping after updates.
4. No public API contract changes are introduced.
