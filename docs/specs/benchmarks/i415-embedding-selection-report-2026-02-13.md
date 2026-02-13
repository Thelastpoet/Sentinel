# I-415 Embedding Selection Report (2026-02-13)

## Scope

- Task: `I-415`
- Corpus: `data/eval/embedding_bakeoff_v1.jsonl`
- Lexicon source: `data/lexicon_seed.json`
- Similarity threshold: `0.35`
- JSON artifact: `docs/specs/benchmarks/i415-embedding-selection-report-2026-02-13.json`

## Candidate Results

| Candidate | Type | Available | Weighted F1 | Benign FP | P95 ms |
|---|---|---:|---:|---:|---:|
| `hash-bow-v1` | baseline | yes | 0.755952 | 0.000000 | 0.146160 |
| `e5-multilingual-small` | target | no (disabled optional runtime) | n/a | n/a | n/a |
| `labse` | target | no (disabled optional runtime) | n/a | n/a | n/a |
| `hash-token-v1` | documented substitute | yes | 0.677381 | 0.125000 | 0.041308 |
| `hash-chargram-v1` | documented substitute | yes | 0.658333 | 0.125000 | 0.347397 |

## Gate Evaluation

The two available substitutes did not pass the quality/safety gate:

- neither reached quality improvement threshold versus baseline;
- both regressed benign false-positive rate beyond allowed tolerance.

## Decision

Selected strategy for current cycle: **`hash-bow-v1` remains active baseline**.

Rationale:

1. Highest weighted F1 among available candidates.
2. No benign FP regression.
3. Meets runtime latency constraints with wide margin in bakeoff profile.

## Rollback Path

Rollback target is unchanged baseline (`hash-bow-v1`), already active.

If a future promoted candidate regresses:

1. set runtime provider selection back to `hash-bow-v1`;
2. invalidate candidate selection cache/restart API process;
3. re-run benchmark + moderation regression suite;
4. record rollback event in release/governance evidence bundle.

## Follow-up

- Re-run bakeoff with optional-model runtime enabled when `I-420` ML extras are available.
- Revisit selection decision after `I-418` dataset expansion.
