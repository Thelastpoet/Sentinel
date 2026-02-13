# Engineering Lessons

## 2026-02-13 - Bakeoff Selection Test Assumptions

- Issue: A test incorrectly assumed baseline (`hash-bow-v1`) would always be selected in embedding bakeoff runs.
- Root cause: The selection gate can validly choose a substitute candidate on small corpora when quality/safety criteria are met.
- Rule going forward: Tests for selection systems must validate gate semantics (eligible candidate + qualification evidence), not hardcode one winner unless the spec explicitly requires deterministic winner lock.
- Applied in: `tests/test_embedding_bakeoff.py`

## 2026-02-13 - Dataset Pipeline Failure-Path Coverage

- Issue: Initial `I-418` tests mainly covered happy paths and artifact existence.
- Root cause: Bootstrap milestone prioritized delivery speed over gate-failure assertions.
- Rule going forward: Validation pipelines must include at least one explicit failure-path test for each acceptance gate (coverage/threshold/metadata mismatch).
- Applied in: `tests/test_validate_ml_dataset_release.py` and follow-on `I-417` calibration tests.

## 2026-02-13 - Governance-Target Threshold Selection

- Issue: `I-417` selected thresholds had equal F1 to baseline on the current synthetic corpus.
- Root cause: Multiple candidates tied on quality metrics; governance-target tie-break drove promotion.
- Rule going forward: Calibration reports must explicitly state whether promotion is quality-improving or non-regressing governance alignment.
- Applied in: `scripts/calibrate_claim_likeness.py`, `docs/specs/benchmarks/i417-threshold-promotion-decision-2026-02-13.md`.
