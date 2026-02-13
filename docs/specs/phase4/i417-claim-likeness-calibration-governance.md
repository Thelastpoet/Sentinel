# I-417: Claim-Likeness Calibration and Governance Thresholds

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-13
- Scope: Calibrate claim-likeness thresholds with labeled data and governance sign-off
- Task linkage: `I-417` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 9.1, Sec. 13.2, Sec. 21.2), `docs/specs/phase4/i412-disinfo-claim-likeness-baseline.md`, `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`

## 1. Objective

Move claim-likeness from static baseline thresholds to evidence-backed calibrated thresholds per governance process.

## 2. Required Behavior

1. Use labeled calibration corpus produced by `I-418`.
2. Evaluate false-positive/false-negative tradeoffs by language/subgroup.
3. Propose threshold updates with explicit safety impact analysis.
4. Require governance sign-off before promoting new thresholds.

Calibration corpus requirements (normative):

1. Minimum corpus size: 2,000 labeled items before first threshold promotion.
2. Language mix must include Tier-1 languages at minimum.
3. Labeling process must include:
   - annotation guideline version,
   - inter-annotator agreement report,
   - reviewer/owner accountability trail.

Current corpus reference (from `I-418`):

- `data/datasets/ml_calibration/v1/corpus.jsonl`
- `data/datasets/ml_calibration/v1/release_metadata.json`

## 3. Acceptance Criteria

1. Calibration report includes per-language and subgroup metrics.
2. Threshold changes are versioned in policy config and auditable.
3. Regression tests verify deterministic score-to-band mapping after updates.
4. No public API contract changes are introduced.
5. Calibration evidence references dataset artifact and annotation provenance.

## 4. Implementation Notes

1. Calibration engine:
   - `src/sentinel_core/claim_calibration.py`
2. Calibration report generator:
   - `scripts/calibrate_claim_likeness.py`
3. Calibration evidence artifacts:
   - `docs/specs/benchmarks/i417-claim-likeness-calibration-2026-02-13.json`
   - `docs/specs/benchmarks/i417-claim-likeness-calibration-2026-02-13.md`
   - `docs/specs/benchmarks/i417-threshold-promotion-decision-2026-02-13.md`
4. Policy thresholds and versioning:
   - `config/policy/default.json`
   - calibrated `claim_likeness` thresholds promoted and policy version bumped.
5. Regression coverage:
   - `tests/test_claim_calibration.py`
   - `tests/test_calibrate_claim_likeness_script.py`

## 5. Verification Commands

```bash
python -m pytest -q tests/test_claim_calibration.py tests/test_calibrate_claim_likeness_script.py tests/test_claim_likeness.py tests/test_policy_claim_likeness.py
python scripts/calibrate_claim_likeness.py --pretty
python -m pytest -q
python scripts/check_contract.py
```
