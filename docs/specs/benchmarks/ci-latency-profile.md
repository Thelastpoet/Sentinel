# CI Latency Benchmark Profile

## Purpose

Defines the canonical CI benchmark configuration used by `I-410` to enforce the hot-path latency budget.

## Baseline Profile

1. Runner class:
   - GitHub-hosted Linux runner (`ubuntu-latest`) unless explicitly changed by approved spec update.
2. Benchmark command:
   - `python scripts/benchmark_hot_path.py --iterations 300 --warmup 30 --p95-budget-ms 150`
3. Runtime assumptions:
   - isolated CI job with no parallel test workload in the same step;
   - default policy config and seeded lexicon.
4. Variance handling:
   - no variance waiver by default;
   - any temporary variance waiver requires explicit PR note and linked issue with expiry date.

## Change Control

Any modification to runner profile, command parameters, or budget must update:

1. this document;
2. `docs/specs/phase4/i410-latency-slo-ci-gate.md`;
3. CI workflow implementation in the same PR.
