from __future__ import annotations

from sentinel_core.annotation_pipeline import AnnotationSample, load_annotation_samples
from sentinel_core.claim_calibration import (
    evaluate_threshold_candidate,
    select_calibrated_thresholds,
)


def test_evaluate_threshold_candidate_returns_language_and_subgroup_metrics() -> None:
    samples = [
        AnnotationSample(
            sample_id="s1",
            text="IEBC results were manipulated in 5 stations.",
            language="en",
            labels=["DISINFO_RISK"],
            is_benign_political=False,
            subgroup="nairobi-urban",
            source="test",
            annotation_guide_version="v1",
            qa_status="accepted",
        ),
        AnnotationSample(
            sample_id="s2",
            text="Tuongee sera kwa amani bila vurugu.",
            language="sw",
            labels=["BENIGN_POLITICAL_SPEECH"],
            is_benign_political=True,
            subgroup="coast-urban",
            source="test",
            annotation_guide_version="v1",
            qa_status="accepted",
        ),
    ]
    summary = evaluate_threshold_candidate(
        samples,
        medium_threshold=0.45,
        high_threshold=0.75,
        require_election_anchor=True,
    )
    assert summary.global_metrics.tp >= 0
    assert "en" in summary.language_metrics
    assert "sw" in summary.language_metrics
    assert "nairobi-urban" in summary.subgroup_metrics
    assert "coast-urban" in summary.subgroup_metrics


def test_select_calibrated_thresholds_prefers_conservative_non_regressing_candidate() -> None:
    samples = load_annotation_samples("data/datasets/ml_calibration/v1/corpus.jsonl")
    baseline, selected, _ = select_calibrated_thresholds(
        samples,
        baseline_medium=0.40,
        baseline_high=0.70,
        require_election_anchor=True,
    )
    assert selected.candidate.medium_threshold >= baseline.candidate.medium_threshold
    assert selected.candidate.high_threshold >= baseline.candidate.high_threshold
    assert selected.benign_fp_rate <= (baseline.benign_fp_rate + 0.01)
