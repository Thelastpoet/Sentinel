# I-418: ML Dataset and Annotation Pipeline for Calibration

## 0. Document Control

- Status: Ratified for implementation
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
