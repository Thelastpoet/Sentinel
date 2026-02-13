# I-410: Latency SLO CI Gate (`P95 < 150ms`)

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Automated latency budget enforcement in CI
- Task linkage: `I-410` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 3.1, Sec. 19), `scripts/benchmark_hot_path.py`

## 1. Objective

Convert latency target from an informational benchmark to an enforced CI gate.

## 2. Gate Requirements

1. Run hot-path benchmark with fixed iterations/warmup in CI.
2. Enforce failure when p95 exceeds configured budget (default 150ms).
3. Persist benchmark summary artifact for review on each run.

## 3. Runtime Constraints

1. Benchmark profile must be stable and documented (CPU class, env assumptions).
2. Gate should tolerate known variance window only when explicitly justified.
3. Budget changes require spec/doc update in same PR.

Benchmark profile documentation path:

- `docs/specs/benchmarks/ci-latency-profile.md`
- must define CI runner class, runtime flags, sample sizes, and variance assumptions.

## 4. Acceptance Criteria

1. CI includes a non-optional latency-gate step.
2. Step returns non-zero when p95 > budget.
3. Benchmark report artifact is uploaded and retained.
4. Checklist alignment: `docs/master.md` Sec. 19 item 9 becomes continuously verifiable.

## 5. Implementation Notes

1. CI gate command is in `.github/workflows/ci.yml`:
   - `python scripts/benchmark_hot_path.py --iterations 300 --warmup 30 --p95-budget-ms 150 --json > latency-benchmark.json`
2. Artifact upload is enforced in the same workflow via `actions/upload-artifact@v4`:
   - artifact name: `latency-benchmark`
   - retention: 14 days.
