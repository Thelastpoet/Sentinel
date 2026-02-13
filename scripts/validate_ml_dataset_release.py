from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel_core.annotation_pipeline import (
    load_annotation_samples,
    load_double_annotation_samples,
    summarize_annotation_corpus,
    summarize_inter_annotator_agreement,
)


def _read_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"{field_name} must be an integer")


def _read_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a float")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise ValueError(f"{field_name} must be a float")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate ML calibration dataset release artifacts.",
    )
    parser.add_argument(
        "--corpus-path",
        default="data/datasets/ml_calibration/v1/corpus.jsonl",
        help="Path to adjudicated corpus JSONL.",
    )
    parser.add_argument(
        "--double-annotation-path",
        default="data/datasets/ml_calibration/v1/double_annotation_sample.jsonl",
        help="Path to double annotation JSONL.",
    )
    parser.add_argument(
        "--metadata-path",
        default="data/datasets/ml_calibration/v1/release_metadata.json",
        help="Path to release metadata JSON.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=2000,
        help="Minimum sample count gate.",
    )
    parser.add_argument(
        "--min-binary-harmful-kappa",
        type=float,
        default=0.60,
        help="Minimum acceptable binary harmful Cohen's kappa.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print human-readable output.",
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    corpus_samples = load_annotation_samples(args.corpus_path)
    corpus_summary = summarize_annotation_corpus(corpus_samples, min_samples=args.min_samples)
    double_samples = load_double_annotation_samples(args.double_annotation_path)
    agreement_summary = summarize_inter_annotator_agreement(double_samples)

    metadata_path = Path(args.metadata_path)
    if not metadata_path.exists():
        raise FileNotFoundError(metadata_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata_sample_count = _read_int(metadata.get("sample_count", 0), field_name="sample_count")
    corpus_sample_count = _read_int(
        corpus_summary["sample_count"], field_name="corpus_sample_count"
    )
    if metadata_sample_count != corpus_sample_count:
        raise ValueError(
            "metadata sample_count mismatch: "
            f"metadata={metadata_sample_count} corpus={corpus_summary['sample_count']}"
        )
    if not bool(corpus_summary["tier1_coverage_complete"]):
        raise ValueError("tier1 language coverage gate failed")
    if not bool(corpus_summary["meets_minimum_sample_count"]):
        raise ValueError("minimum sample gate failed")
    binary_harmful_kappa = _read_float(
        agreement_summary["binary_harmful_kappa"],
        field_name="binary_harmful_kappa",
    )
    if binary_harmful_kappa < args.min_binary_harmful_kappa:
        raise ValueError(
            "binary harmful kappa gate failed: "
            f"{binary_harmful_kappa} < {args.min_binary_harmful_kappa}"
        )

    report = {
        "ok": True,
        "sample_count": corpus_sample_count,
        "language_counts": corpus_summary["language_counts"],
        "binary_harmful_kappa": binary_harmful_kappa,
        "exact_label_set_match_rate": agreement_summary["exact_label_set_match_rate"],
        "metadata_path": str(metadata_path),
    }
    if args.pretty:
        print(
            "ml-dataset-validate "
            f"ok={report['ok']} "
            f"sample_count={report['sample_count']} "
            f"binary_harmful_kappa={report['binary_harmful_kappa']}"
        )
        print(f"language_counts={report['language_counts']}")
        print(f"metadata={report['metadata_path']}")
    else:
        print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
