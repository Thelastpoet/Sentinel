from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel_core.embedding_bakeoff import run_embedding_bakeoff


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark embedding candidates against retrieval-oriented eval corpus."
    )
    parser.add_argument(
        "--input-path",
        default="data/eval/embedding_bakeoff_v1.jsonl",
        help="Evaluation corpus path (JSONL).",
    )
    parser.add_argument(
        "--lexicon-path",
        default="data/lexicon_seed.json",
        help="Lexicon seed path used for retrieval candidates.",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.35,
        help="Similarity threshold for mapping top retrieval candidate to a harm label.",
    )
    parser.add_argument(
        "--enable-optional-models",
        action="store_true",
        help="Enable optional non-baseline model candidates when local runtime supports them.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Optional output path for JSON report.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    report = run_embedding_bakeoff(
        input_path=args.input_path,
        lexicon_path=args.lexicon_path,
        similarity_threshold=args.similarity_threshold,
        enable_optional_models=args.enable_optional_models,
    )
    payload = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    print(payload)
    if args.output_path:
        Path(args.output_path).write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
