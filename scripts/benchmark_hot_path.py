from __future__ import annotations

import argparse
import json
import sys
import time

from sentinel_api.benchmark import summarize_latency
from sentinel_api.policy import moderate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark Sentinel moderation hot-path latency"
    )
    parser.add_argument(
        "--text",
        default="We should discuss policy peacefully.",
        help="Input text used for benchmark calls",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Number of measured moderation calls",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=20,
        help="Number of warm-up calls before measurement",
    )
    parser.add_argument(
        "--p95-budget-ms",
        type=float,
        default=None,
        help="Optional p95 budget. Exits non-zero when exceeded.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output",
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    if args.iterations <= 0:
        raise ValueError("--iterations must be > 0")
    if args.warmup < 0:
        raise ValueError("--warmup must be >= 0")

    for _ in range(args.warmup):
        moderate(args.text)

    latencies_ms: list[float] = []
    for _ in range(args.iterations):
        start = time.perf_counter()
        moderate(args.text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed_ms)

    summary = summarize_latency(latencies_ms)
    output = {
        "iterations": args.iterations,
        "warmup": args.warmup,
        "text_length": len(args.text),
        **summary,
    }

    if args.json:
        print(json.dumps(output))
    else:
        print(
            "benchmark-hot-path "
            f"iterations={args.iterations} warmup={args.warmup} "
            f"min_ms={output['min_ms']:.2f} mean_ms={output['mean_ms']:.2f} "
            f"p95_ms={output['p95_ms']:.2f} max_ms={output['max_ms']:.2f}"
        )

    budget = args.p95_budget_ms
    if budget is not None and output["p95_ms"] > budget:
        print(
            f"benchmark-hot-path: p95 {output['p95_ms']:.2f}ms exceeds budget {budget:.2f}ms",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
