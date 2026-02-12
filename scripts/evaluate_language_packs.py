from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel_api.policy import moderate
from sentinel_core.eval_harness import evaluate_samples, load_eval_samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run per-language and bias evaluation harness for moderation quality."
    )
    parser.add_argument(
        "--input-path",
        required=True,
        help="Path to JSONL evaluation set.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Optional path to write JSON report.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on number of samples evaluated.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    samples = load_eval_samples(args.input_path)
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit must be > 0 when provided")
        samples = samples[: args.limit]
    report = evaluate_samples(samples, moderate_fn=moderate)
    payload = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    print(payload)
    if args.output_path:
        Path(args.output_path).write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

