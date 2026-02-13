# I-415 Embedding Bakeoff Profile

## Purpose

Defines the reproducible benchmark setup for embedding candidate selection in `I-415`.

## Corpus

- Retrieval corpus: `data/eval/embedding_bakeoff_v1.jsonl`
- Lexicon source: `data/lexicon_seed.json`
- Sample count: 24
- Label coverage: all five harm labels + benign political speech

## Candidate Set

Required candidates:

1. `hash-bow-v1` (baseline)
2. `e5` family candidate (optional runtime)
3. `LaBSE`-class candidate (optional runtime)

Documented substitutes when optional runtime is unavailable:

1. `hash-token-v1`
2. `hash-chargram-v1`

## Benchmark Command

```bash
python scripts/benchmark_embedding_candidates.py \
  --input-path data/eval/embedding_bakeoff_v1.jsonl \
  --lexicon-path data/lexicon_seed.json \
  --similarity-threshold 0.35 \
  --pretty \
  --output-path docs/specs/benchmarks/i415-embedding-selection-report-2026-02-13.json
```

## Selection Gates

Candidate qualifies only when:

1. quality gate passes:
   - weighted F1 >= baseline * 1.05, OR
   - weighted F1 >= baseline * 0.99 and p95 latency <= baseline * 0.8
2. safety gate passes:
   - benign FP rate <= baseline benign FP + 0.01

If no candidate qualifies, baseline remains selected and rationale is recorded.
