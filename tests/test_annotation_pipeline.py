from __future__ import annotations

import json

from sentinel_core.annotation_pipeline import (
    load_annotation_samples,
    load_double_annotation_samples,
    summarize_annotation_corpus,
    summarize_inter_annotator_agreement,
)


def _write_jsonl(path, rows) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")


def test_annotation_corpus_summary_reports_tier1_coverage(tmp_path) -> None:
    rows = [
        {
            "id": "sample-1",
            "text": "We should debate peacefully.",
            "language": "en",
            "labels": ["BENIGN_POLITICAL_SPEECH"],
            "is_benign_political": True,
            "subgroup": "nairobi-urban",
            "source": "synthetic_bootstrap",
            "annotation_guide_version": "ml-annotation-guide-v1",
            "qa_status": "accepted",
        },
        {
            "id": "sample-2",
            "text": "Tukutane usiku tuwashambulie.",
            "language": "sw",
            "labels": ["INCITEMENT_VIOLENCE"],
            "is_benign_political": False,
            "subgroup": "western-rural",
            "source": "synthetic_bootstrap",
            "annotation_guide_version": "ml-annotation-guide-v1",
            "qa_status": "accepted",
        },
        {
            "id": "sample-3",
            "text": "Maze wamepika story ya tally.",
            "language": "sh",
            "labels": ["DISINFO_RISK"],
            "is_benign_political": False,
            "subgroup": "coast-urban",
            "source": "synthetic_bootstrap",
            "annotation_guide_version": "ml-annotation-guide-v1",
            "qa_status": "accepted",
        },
    ]
    dataset_path = tmp_path / "corpus.jsonl"
    _write_jsonl(dataset_path, rows)

    samples = load_annotation_samples(dataset_path)
    summary = summarize_annotation_corpus(samples, min_samples=3)
    assert summary["sample_count"] == 3
    assert summary["tier1_coverage_complete"] is True
    assert summary["meets_minimum_sample_count"] is True


def test_inter_annotator_agreement_summary_has_expected_fields(tmp_path) -> None:
    rows = [
        {
            "id": "pair-1",
            "language": "en",
            "annotator_a_labels": ["DISINFO_RISK"],
            "annotator_b_labels": ["DISINFO_RISK"],
            "adjudicated_labels": ["DISINFO_RISK"],
        },
        {
            "id": "pair-2",
            "language": "sw",
            "annotator_a_labels": ["BENIGN_POLITICAL_SPEECH"],
            "annotator_b_labels": ["DOGWHISTLE_WATCH"],
            "adjudicated_labels": ["DOGWHISTLE_WATCH"],
        },
        {
            "id": "pair-3",
            "language": "sh",
            "annotator_a_labels": ["INCITEMENT_VIOLENCE"],
            "annotator_b_labels": ["INCITEMENT_VIOLENCE"],
            "adjudicated_labels": ["INCITEMENT_VIOLENCE"],
        },
    ]
    pairs_path = tmp_path / "double.jsonl"
    _write_jsonl(pairs_path, rows)

    samples = load_double_annotation_samples(pairs_path)
    summary = summarize_inter_annotator_agreement(samples)
    assert summary["sample_count"] == 3
    assert 0.0 <= summary["exact_label_set_match_rate"] <= 1.0
    assert -1.0 <= summary["binary_harmful_kappa"] <= 1.0
    per_label = summary["per_label_kappa"]
    assert isinstance(per_label, dict)
    assert "DISINFO_RISK" in per_label
