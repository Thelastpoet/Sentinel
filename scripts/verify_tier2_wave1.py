from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel_langpack.wave1 import (
    evaluate_pack_gates,
    load_wave1_registry,
    wave1_packs_in_priority_order,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Tier-2 Wave 1 language-pack gate readiness."
    )
    parser.add_argument(
        "--registry-path",
        default="data/langpacks/registry.json",
        help="Path to wave1 language-pack registry file.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Optional path to write JSON gate report.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    registry_path = Path(args.registry_path).resolve()
    registry = load_wave1_registry(registry_path)
    ordered = wave1_packs_in_priority_order(registry)
    results = [evaluate_pack_gates(pack, registry_path=registry_path) for pack in ordered]

    payload = {
        "wave": registry.wave,
        "all_passed": all(result.passed for result in results),
        "results": [
            {
                "language": result.language,
                "pack_version": result.pack_version,
                "passed": result.passed,
                "sample_count": result.sample_count,
                "code_switched_ratio": result.code_switched_ratio,
                "gate_failures": result.gate_failures,
            }
            for result in results
        ],
    }
    rendered = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True)
    print(rendered)
    if args.output_path:
        Path(args.output_path).write_text(rendered + "\n", encoding="utf-8")

    if not payload["all_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

