from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sentinel_core.annotation_pipeline import load_annotation_samples
from sentinel_core.claim_calibration import select_calibrated_thresholds
from sentinel_core.policy_config import get_policy_config, reset_policy_config_cache

CALIBRATED_MEDIUM_THRESHOLD = 0.45
CALIBRATED_HIGH_THRESHOLD = 0.75


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate claim-likeness thresholds against labeled corpus.",
    )
    parser.add_argument(
        "--dataset-path",
        default="data/datasets/ml_calibration/v1/corpus.jsonl",
        help="Path to labeled corpus JSONL.",
    )
    parser.add_argument(
        "--output-json",
        default="reports/ml/i417-claim-likeness-calibration-2026-02-13.json",
        help="Path to write calibration report JSON.",
    )
    parser.add_argument(
        "--output-md",
        default="reports/ml/i417-claim-likeness-calibration-2026-02-13.md",
        help="Path to write calibration report markdown.",
    )
    parser.add_argument(
        "--baseline-medium-threshold",
        type=float,
        default=None,
        help="Optional baseline medium threshold override for calibration report.",
    )
    parser.add_argument(
        "--baseline-high-threshold",
        type=float,
        default=None,
        help="Optional baseline high threshold override for calibration report.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print human-readable summary output.",
    )
    return parser.parse_args()


def _to_markdown(report: dict[str, object]) -> str:
    baseline_raw = report.get("baseline")
    selected_raw = report.get("selected")
    if not isinstance(baseline_raw, dict) or not isinstance(selected_raw, dict):
        raise ValueError("report baseline/selected payload is invalid")
    baseline = baseline_raw
    selected = selected_raw
    baseline_candidate = baseline.get("candidate")
    selected_candidate = selected.get("candidate")
    baseline_metrics = baseline.get("global_metrics")
    selected_metrics = selected.get("global_metrics")
    if not isinstance(baseline_candidate, dict) or not isinstance(selected_candidate, dict):
        raise ValueError("report candidate payload is invalid")
    if not isinstance(baseline_metrics, dict) or not isinstance(selected_metrics, dict):
        raise ValueError("report metrics payload is invalid")
    lines = [
        "# I-417 Claim-Likeness Calibration Report",
        "",
        f"- dataset_path: {report['dataset_path']}",
        f"- sample_count: {report['sample_count']}",
        f"- generated_at: {report['generated_at']}",
        "",
        "## Baseline Thresholds",
        "",
        f"- medium_threshold: {baseline_candidate['medium_threshold']}",
        f"- high_threshold: {baseline_candidate['high_threshold']}",
        f"- global_f1: {baseline_metrics['f1']}",
        f"- benign_fp_rate: {baseline['benign_false_positive_rate']}",
        "",
        "## Selected Thresholds",
        "",
        f"- medium_threshold: {selected_candidate['medium_threshold']}",
        f"- high_threshold: {selected_candidate['high_threshold']}",
        f"- global_f1: {selected_metrics['f1']}",
        f"- benign_fp_rate: {selected['benign_false_positive_rate']}",
        "",
        "## Governance Notes",
        "",
        "- Proposed for policy config promotion after governance sign-off.",
        "- No public API contract changes introduced.",
    ]
    return "\n".join(lines) + "\n"


def run() -> int:
    args = parse_args()
    reset_policy_config_cache()
    policy_config = get_policy_config()
    baseline_medium = (
        policy_config.claim_likeness.medium_threshold
        if args.baseline_medium_threshold is None
        else args.baseline_medium_threshold
    )
    baseline_high = (
        policy_config.claim_likeness.high_threshold
        if args.baseline_high_threshold is None
        else args.baseline_high_threshold
    )
    corpus = load_annotation_samples(args.dataset_path)
    baseline, selected, candidate_summaries = select_calibrated_thresholds(
        corpus,
        baseline_medium=baseline_medium,
        baseline_high=baseline_high,
        require_election_anchor=policy_config.claim_likeness.require_election_anchor,
        governance_target_medium=CALIBRATED_MEDIUM_THRESHOLD,
        governance_target_high=CALIBRATED_HIGH_THRESHOLD,
    )

    report = {
        "dataset_path": str(args.dataset_path),
        "sample_count": len(corpus),
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "baseline": baseline.as_dict(),
        "selected": selected.as_dict(),
        "candidate_count": len(candidate_summaries),
        "selected_is_baseline": baseline.candidate == selected.candidate,
        "governance_target_thresholds": {
            "medium_threshold": CALIBRATED_MEDIUM_THRESHOLD,
            "high_threshold": CALIBRATED_HIGH_THRESHOLD,
        },
        "policy_require_election_anchor": policy_config.claim_likeness.require_election_anchor,
        "active_policy_thresholds": {
            "medium_threshold": policy_config.claim_likeness.medium_threshold,
            "high_threshold": policy_config.claim_likeness.high_threshold,
        },
        "annotation_guide_version": "ml-annotation-guide-v1",
        "dataset_release_metadata_path": "data/datasets/ml_calibration/v1/release_metadata.json",
    }

    output_json_path = Path(args.output_json)
    output_md_path = Path(args.output_md)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_md_path.write_text(_to_markdown(report), encoding="utf-8")

    if args.pretty:
        baseline_tuple = (
            f"{baseline.candidate.medium_threshold:.2f}",
            f"{baseline.candidate.high_threshold:.2f}",
        )
        selected_tuple = (
            f"{selected.candidate.medium_threshold:.2f}",
            f"{selected.candidate.high_threshold:.2f}",
        )
        print(
            "claim-calibration "
            f"samples={report['sample_count']} "
            f"baseline=({baseline_tuple[0]},{baseline_tuple[1]}) "
            f"selected=({selected_tuple[0]},{selected_tuple[1]}) "
            f"selected_f1={selected.global_metrics.f1:.3f} "
            f"baseline_f1={baseline.global_metrics.f1:.3f}"
        )
        print(f"report_json={output_json_path}")
        print(f"report_md={output_md_path}")
    else:
        print(
            json.dumps(
                {
                    "sample_count": report["sample_count"],
                    "selected_medium_threshold": selected.candidate.medium_threshold,
                    "selected_high_threshold": selected.candidate.high_threshold,
                    "selected_f1": round(selected.global_metrics.f1, 6),
                    "baseline_f1": round(baseline.global_metrics.f1, 6),
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
