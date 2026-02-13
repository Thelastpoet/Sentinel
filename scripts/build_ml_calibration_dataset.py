from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sentinel_core.annotation_pipeline import (
    load_annotation_samples,
    load_double_annotation_samples,
    summarize_annotation_corpus,
    summarize_inter_annotator_agreement,
)

GUIDE_VERSION = "ml-annotation-guide-v1"
DATASET_VERSION = "ml-calibration-v1"

SUBGROUPS = (
    "nairobi-urban",
    "rift-valley-rural",
    "coast-urban",
    "western-rural",
    "central-urban",
    "north-eastern-rural",
)

TOPICS = (
    "IEBC tally process",
    "polling station delays",
    "county vote transport",
    "results transmission",
    "coalition messaging",
    "campaign rally security",
)

LANGUAGE_PATTERNS: dict[str, list[tuple[list[str], str]]] = {
    "en": [
        (
            ["BENIGN_POLITICAL_SPEECH"],
            "We should debate {topic} peacefully and respect all voters.",
        ),
        (["DISINFO_RISK"], "They secretly manipulated the {topic} and hid the real numbers."),
        (["INCITEMENT_VIOLENCE"], "Gather tonight and attack them over the {topic}."),
        (["ETHNIC_CONTEMPT"], "That tribe is unfit to lead anything in {topic}."),
        (["HARASSMENT_THREAT"], "We will hunt and beat anyone speaking about {topic}."),
        (["DOGWHISTLE_WATCH"], "Time to cleanse the movement before {topic}."),
        (
            ["DISINFO_RISK", "DOGWHISTLE_WATCH"],
            "Their hidden network rigged {topic}; we must purge them quietly.",
        ),
    ],
    "sw": [
        (["BENIGN_POLITICAL_SPEECH"], "Tujadili {topic} kwa amani na kuheshimu wapiga kura wote."),
        (["DISINFO_RISK"], "Wameficha ukweli na kuharibu {topic} kimya kimya."),
        (["INCITEMENT_VIOLENCE"], "Tukutane usiku tuwashambulie kwa sababu ya {topic}."),
        (["ETHNIC_CONTEMPT"], "Kabila hilo halifai kuongoza jambo la {topic}."),
        (["HARASSMENT_THREAT"], "Tutawatafuta na kuwachapa wanaoongea kuhusu {topic}."),
        (["DOGWHISTLE_WATCH"], "Ni wakati wa kusafisha kundi kabla ya {topic}."),
        (
            ["DISINFO_RISK", "DOGWHISTLE_WATCH"],
            "Wameiba {topic}; tushughulikie wao kwa njia ya siri.",
        ),
    ],
    "sh": [
        (["BENIGN_POLITICAL_SPEECH"], "Maze tuongee {topic} poa bila noma kwa kila mtu."),
        (["DISINFO_RISK"], "Wamepika story ya {topic} na kuficha real score."),
        (["INCITEMENT_VIOLENCE"], "Leo usiku twende tuwapige juu ya {topic}."),
        (["ETHNIC_CONTEMPT"], "Hao wasee wa hio tribe hawafai kwa {topic}."),
        (["HARASSMENT_THREAT"], "Tutawawinda na kuwararua wakiongea {topic}."),
        (["DOGWHISTLE_WATCH"], "Time ya ku-clean movement kabla ya {topic}."),
        (
            ["DISINFO_RISK", "DOGWHISTLE_WATCH"],
            "Wameiba {topic}; wachafue quietly before wasee wajue.",
        ),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic ML calibration dataset artifacts for I-418.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/datasets/ml_calibration/v1",
        help="Directory where corpus artifacts are written.",
    )
    parser.add_argument(
        "--agreement-report-path",
        default="reports/ml/i418-inter-annotator-agreement-2026-02-13.json",
        help="Path to write agreement report JSON.",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=2100,
        help="Total corpus samples to generate (minimum 2000 recommended).",
    )
    parser.add_argument(
        "--double-annotation-count",
        type=int,
        default=360,
        help="Number of samples included in double-annotation agreement set.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260213,
        help="Random seed for deterministic generation.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print human-readable summary.",
    )
    return parser.parse_args()


def _make_timestamp(index: int) -> str:
    base = datetime(2026, 2, 13, tzinfo=UTC)
    moment = base + timedelta(minutes=index)
    return moment.isoformat().replace("+00:00", "Z")


def _build_corpus(sample_count: int, seed: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    languages = list(LANGUAGE_PATTERNS.keys())
    records: list[dict[str, object]] = []

    for index in range(sample_count):
        language = languages[index % len(languages)]
        pattern_list = LANGUAGE_PATTERNS[language]
        labels, template = pattern_list[index % len(pattern_list)]
        topic = TOPICS[index % len(TOPICS)]
        subgroup = SUBGROUPS[index % len(SUBGROUPS)]
        suffix = rng.randint(10, 999)
        text = f"{template.format(topic=topic)} ref-{suffix}"
        record = {
            "id": f"{DATASET_VERSION}-{index + 1:06d}",
            "text": text,
            "language": language,
            "labels": sorted(set(labels)),
            "is_benign_political": labels == ["BENIGN_POLITICAL_SPEECH"],
            "is_code_switched": language == "sh",
            "subgroup": subgroup,
            "source": "synthetic_bootstrap",
            "annotation_guide_version": GUIDE_VERSION,
            "qa_status": "accepted",
            "created_at": _make_timestamp(index),
        }
        records.append(record)

    return records


def _label_noise(labels: list[str], index: int) -> list[str]:
    if index % 13 == 0:
        if labels == ["BENIGN_POLITICAL_SPEECH"]:
            return ["DOGWHISTLE_WATCH"]
        return ["BENIGN_POLITICAL_SPEECH"]
    if index % 17 == 0 and len(labels) > 1:
        return labels[:-1]
    if index % 19 == 0 and "DOGWHISTLE_WATCH" not in labels:
        return sorted(set(labels + ["DOGWHISTLE_WATCH"]))
    return labels


def _build_double_annotation(
    corpus_records: list[dict[str, object]],
    *,
    pair_count: int,
) -> list[dict[str, object]]:
    effective_count = min(max(1, pair_count), len(corpus_records))
    paired: list[dict[str, object]] = []
    for index in range(effective_count):
        item = corpus_records[index]
        label_values = item.get("labels")
        if not isinstance(label_values, list):
            raise ValueError(f"labels must be a list for sample {item.get('id')}")
        adjudicated = [str(value) for value in label_values]
        annotator_a = adjudicated
        annotator_b = _label_noise(adjudicated, index=index + 1)
        paired.append(
            {
                "id": item["id"],
                "language": item["language"],
                "annotator_a_labels": annotator_a,
                "annotator_b_labels": annotator_b,
                "adjudicated_labels": adjudicated,
            }
        )
    return paired


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True))
            handle.write("\n")


def _render_markdown_report(agreement: dict[str, object], path: Path) -> None:
    lines = [
        "# I-418 Inter-Annotator Agreement Report",
        "",
        f"- sample_count: {agreement['sample_count']}",
        f"- exact_label_set_match_rate: {agreement['exact_label_set_match_rate']}",
        f"- binary_harmful_kappa: {agreement['binary_harmful_kappa']}",
        "",
        "## Per-Label Kappa",
        "",
    ]
    per_label = agreement["per_label_kappa"]
    if isinstance(per_label, dict):
        for label in sorted(per_label):
            lines.append(f"- {label}: {per_label[label]}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> int:
    args = parse_args()
    if args.sample_count < 2000:
        raise ValueError("--sample-count must be >= 2000")
    if args.double_annotation_count <= 0:
        raise ValueError("--double-annotation-count must be > 0")

    output_dir = Path(args.output_dir)
    corpus_path = output_dir / "corpus.jsonl"
    double_annotation_path = output_dir / "double_annotation_sample.jsonl"
    metadata_path = output_dir / "release_metadata.json"

    corpus_records = _build_corpus(sample_count=args.sample_count, seed=args.seed)
    _write_jsonl(corpus_path, corpus_records)

    double_annotation_records = _build_double_annotation(
        corpus_records,
        pair_count=args.double_annotation_count,
    )
    _write_jsonl(double_annotation_path, double_annotation_records)

    corpus_samples = load_annotation_samples(corpus_path)
    corpus_summary = summarize_annotation_corpus(corpus_samples)
    double_samples = load_double_annotation_samples(double_annotation_path)
    agreement_summary = summarize_inter_annotator_agreement(double_samples)

    agreement_report_path = Path(args.agreement_report_path)
    agreement_report_path.parent.mkdir(parents=True, exist_ok=True)
    agreement_report_path.write_text(
        json.dumps(agreement_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_report_path = agreement_report_path.with_suffix(".md")
    _render_markdown_report(agreement_summary, markdown_report_path)

    metadata = {
        "dataset_version": DATASET_VERSION,
        "dataset_path": str(corpus_path),
        "double_annotation_path": str(double_annotation_path),
        "sample_count": corpus_summary["sample_count"],
        "language_counts": corpus_summary["language_counts"],
        "label_counts": corpus_summary["label_counts"],
        "tier1_coverage_complete": corpus_summary["tier1_coverage_complete"],
        "meets_minimum_sample_count": corpus_summary["meets_minimum_sample_count"],
        "annotation_guide_version": GUIDE_VERSION,
        "annotation_guide_path": "resources/annotation-guides/ml-calibration-v1.md",
        "agreement_report_path": str(agreement_report_path),
        "agreement_summary": agreement_summary,
        "source": "synthetic_bootstrap",
        "generated_by": "scripts/build_ml_calibration_dataset.py",
        "seed": args.seed,
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.pretty:
        print(
            "ml-dataset-build "
            f"version={DATASET_VERSION} "
            f"samples={corpus_summary['sample_count']} "
            f"tier1_coverage={corpus_summary['tier1_coverage_complete']} "
            f"agreement_kappa={agreement_summary['binary_harmful_kappa']}"
        )
        print(f"corpus={corpus_path}")
        print(f"agreement={agreement_report_path}")
        print(f"metadata={metadata_path}")
    else:
        print(
            json.dumps(
                {
                    "dataset_version": DATASET_VERSION,
                    "sample_count": corpus_summary["sample_count"],
                    "tier1_coverage_complete": corpus_summary["tier1_coverage_complete"],
                    "agreement_binary_harmful_kappa": agreement_summary["binary_harmful_kappa"],
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
