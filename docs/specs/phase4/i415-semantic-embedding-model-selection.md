# I-415: Semantic Embedding Model Selection and Gate

## 0. Document Control

- Status: Ratified for implementation
- Effective date: 2026-02-13
- Scope: Select first production embedding model using quality/latency benchmark evidence
- Task linkage: `I-415` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 3.1, Sec. 8.2, Sec. 20), `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`

## 1. Objective

Replace or validate `hash-bow-v1` with evidence-driven model selection that respects hot-path latency and safety constraints.

## 2. Required Behavior

1. Define evaluation dataset(s) and scoring protocol for candidate embeddings.
2. Benchmark baseline plus candidate list:
   - `hash-bow-v1` (current baseline),
   - multilingual `e5` family candidate,
   - `LaBSE`-class candidate (or documented substitute if unavailable).
3. Record latency, precision/recall, and false-positive impacts by language.
4. Approve one default embedding strategy with rollback path.

Data dependency:

1. Reuse `I-418` corpus where applicable and add retrieval-specific benchmark set if needed.

Evaluation criteria (normative):

1. Quality gate:
   - weighted F1 for disinfo/hate retrieval must improve by >= 5% versus baseline
     OR baseline-equivalent performance with >= 20% latency reduction.
2. Safety gate:
   - benign political false-positive rate must not regress by > 1 percentage point.
3. Latency gate:
   - end-to-end hot path remains within P95 `<150ms` with model path enabled.
4. Availability gate:
   - timeout/error fallback behavior verified with deterministic baseline continuity.

## 3. Acceptance Criteria

1. Reproducible benchmark report is committed under `docs/specs/benchmarks/`.
2. Selected strategy has explicit quality and latency tradeoff rationale.
3. Selection decision updates `docs/master.md` Sec. 20 decision state.
4. Rollback configuration to baseline strategy is documented and tested.
5. Candidate model list and benchmark corpus definition are documented in the report.
