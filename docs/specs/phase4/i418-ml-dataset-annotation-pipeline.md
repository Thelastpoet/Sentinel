# I-418: ML Dataset and Annotation Pipeline for Calibration

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-13
- Scope: Create labeled corpus and annotation process for ML calibration/promotion
- Task linkage: `I-418` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 13.2, Sec. 21.2), `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`

## 1. Objective

Establish a reproducible, governed data pipeline for claim-likeness and multi-label model evaluation/calibration.

## 2. Required Behavior

1. Define dataset schema and storage layout for labeled moderation examples.
2. Define annotation guide and reviewer workflow.
3. Produce initial labeled corpus for calibration/promotion gates.
4. Record provenance metadata for each dataset release.

## 3. Acceptance Criteria

1. Initial corpus has >= 2,000 labeled examples with Tier-1 language coverage.
2. Annotation guide and QA process are documented.
3. Inter-annotator agreement is measured and reported.
4. Dataset release artifact is versioned and linked in calibration specs.

## 4. Implementation Notes

1. Pipeline module:
   - `src/sentinel_core/annotation_pipeline.py`
2. Dataset build command:
   - `scripts/build_ml_calibration_dataset.py`
3. Dataset validation command:
   - `scripts/validate_ml_dataset_release.py`
4. Versioned dataset artifacts:
   - `data/datasets/ml_calibration/v1/corpus.jsonl`
   - `data/datasets/ml_calibration/v1/double_annotation_sample.jsonl`
   - `data/datasets/ml_calibration/v1/release_metadata.json`
5. Annotation guide:
   - `docs/specs/annotation-guides/ml-calibration-v1.md`
6. Agreement report artifacts:
   - `docs/specs/benchmarks/i418-inter-annotator-agreement-2026-02-13.json`
   - `docs/specs/benchmarks/i418-inter-annotator-agreement-2026-02-13.md`
7. Internal schemas:
   - `docs/specs/schemas/internal/ml-calibration-sample.schema.json`
   - `docs/specs/schemas/internal/ml-double-annotation-sample.schema.json`

## 5. Verification Commands

```bash
python -m pytest -q tests/test_annotation_pipeline.py tests/test_build_ml_calibration_dataset.py tests/test_validate_ml_dataset_release.py
python scripts/build_ml_calibration_dataset.py --pretty
python scripts/validate_ml_dataset_release.py --pretty
python scripts/check_contract.py
```
