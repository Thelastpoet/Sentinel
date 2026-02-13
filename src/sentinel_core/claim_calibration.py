from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from sentinel_core.annotation_pipeline import AnnotationSample
from sentinel_core.claim_likeness import assess_claim_likeness


@dataclass(frozen=True)
class BinaryMetrics:
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def precision(self) -> float:
        denominator = self.tp + self.fp
        if denominator <= 0:
            return 0.0
        return self.tp / denominator

    @property
    def recall(self) -> float:
        denominator = self.tp + self.fn
        if denominator <= 0:
            return 0.0
        return self.tp / denominator

    @property
    def f1(self) -> float:
        precision = self.precision
        recall = self.recall
        denominator = precision + recall
        if denominator <= 0:
            return 0.0
        return (2 * precision * recall) / denominator

    @property
    def false_positive_rate(self) -> float:
        denominator = self.fp + self.tn
        if denominator <= 0:
            return 0.0
        return self.fp / denominator

    def as_dict(self) -> dict[str, float | int]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "precision": round(self.precision, 6),
            "recall": round(self.recall, 6),
            "f1": round(self.f1, 6),
            "false_positive_rate": round(self.false_positive_rate, 6),
        }


@dataclass(frozen=True)
class ThresholdCandidate:
    medium_threshold: float
    high_threshold: float


@dataclass(frozen=True)
class CalibrationSummary:
    candidate: ThresholdCandidate
    global_metrics: BinaryMetrics
    language_metrics: dict[str, BinaryMetrics]
    subgroup_metrics: dict[str, BinaryMetrics]
    benign_fp_rate: float

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate": {
                "medium_threshold": round(self.candidate.medium_threshold, 6),
                "high_threshold": round(self.candidate.high_threshold, 6),
            },
            "global_metrics": self.global_metrics.as_dict(),
            "language_metrics": {
                language: metrics.as_dict()
                for language, metrics in sorted(self.language_metrics.items())
            },
            "subgroup_metrics": {
                subgroup: metrics.as_dict()
                for subgroup, metrics in sorted(self.subgroup_metrics.items())
            },
            "benign_false_positive_rate": round(self.benign_fp_rate, 6),
        }


def _is_disinfo_positive(sample: AnnotationSample) -> bool:
    return "DISINFO_RISK" in set(sample.labels)


def _predict_positive(
    sample: AnnotationSample,
    *,
    medium_threshold: float,
    high_threshold: float,
    require_election_anchor: bool,
) -> bool:
    assessment = assess_claim_likeness(
        sample.text,
        medium_threshold=medium_threshold,
        high_threshold=high_threshold,
    )
    if require_election_anchor and not assessment.has_election_anchor:
        return False
    return assessment.band in {"medium", "high"}


def _update_binary_counters(
    counters: dict[str, int],
    *,
    expected_positive: bool,
    predicted_positive: bool,
) -> None:
    if expected_positive and predicted_positive:
        counters["tp"] += 1
    elif not expected_positive and predicted_positive:
        counters["fp"] += 1
    elif expected_positive and not predicted_positive:
        counters["fn"] += 1
    else:
        counters["tn"] += 1


def _counters_to_metrics(counters: dict[str, int]) -> BinaryMetrics:
    return BinaryMetrics(
        tp=counters.get("tp", 0),
        fp=counters.get("fp", 0),
        fn=counters.get("fn", 0),
        tn=counters.get("tn", 0),
    )


def evaluate_threshold_candidate(
    samples: list[AnnotationSample],
    *,
    medium_threshold: float,
    high_threshold: float,
    require_election_anchor: bool,
) -> CalibrationSummary:
    if not samples:
        raise ValueError("samples must not be empty")
    if medium_threshold >= high_threshold:
        raise ValueError("medium_threshold must be < high_threshold")

    global_counters = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    language_counters: dict[str, dict[str, int]] = {}
    subgroup_counters: dict[str, dict[str, int]] = {}
    benign_total = 0
    benign_fp = 0

    for sample in samples:
        expected_positive = _is_disinfo_positive(sample)
        predicted_positive = _predict_positive(
            sample,
            medium_threshold=medium_threshold,
            high_threshold=high_threshold,
            require_election_anchor=require_election_anchor,
        )
        _update_binary_counters(
            global_counters,
            expected_positive=expected_positive,
            predicted_positive=predicted_positive,
        )

        language_key = sample.language
        language_counters.setdefault(language_key, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        _update_binary_counters(
            language_counters[language_key],
            expected_positive=expected_positive,
            predicted_positive=predicted_positive,
        )

        subgroup_key = sample.subgroup or "unspecified"
        subgroup_counters.setdefault(subgroup_key, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        _update_binary_counters(
            subgroup_counters[subgroup_key],
            expected_positive=expected_positive,
            predicted_positive=predicted_positive,
        )

        if sample.is_benign_political:
            benign_total += 1
            if predicted_positive:
                benign_fp += 1

    global_metrics = _counters_to_metrics(global_counters)
    language_metrics = {
        language: _counters_to_metrics(counters) for language, counters in language_counters.items()
    }
    subgroup_metrics = {
        subgroup: _counters_to_metrics(counters) for subgroup, counters in subgroup_counters.items()
    }
    benign_fp_rate = 0.0 if benign_total <= 0 else benign_fp / benign_total

    return CalibrationSummary(
        candidate=ThresholdCandidate(
            medium_threshold=medium_threshold,
            high_threshold=high_threshold,
        ),
        global_metrics=global_metrics,
        language_metrics=language_metrics,
        subgroup_metrics=subgroup_metrics,
        benign_fp_rate=benign_fp_rate,
    )


def _candidate_grid() -> list[ThresholdCandidate]:
    medium_values = [value / 100.0 for value in range(35, 66, 5)]
    high_values = [value / 100.0 for value in range(60, 91, 5)]
    candidates: list[ThresholdCandidate] = []
    for medium, high in product(medium_values, high_values):
        if medium >= high:
            continue
        if (high - medium) < 0.1:
            continue
        candidates.append(
            ThresholdCandidate(
                medium_threshold=medium,
                high_threshold=high,
            )
        )
    return candidates


def select_calibrated_thresholds(
    samples: list[AnnotationSample],
    *,
    baseline_medium: float,
    baseline_high: float,
    require_election_anchor: bool,
    governance_target_medium: float | None = None,
    governance_target_high: float | None = None,
) -> tuple[CalibrationSummary, CalibrationSummary, list[CalibrationSummary]]:
    baseline = evaluate_threshold_candidate(
        samples,
        medium_threshold=baseline_medium,
        high_threshold=baseline_high,
        require_election_anchor=require_election_anchor,
    )
    candidates = _candidate_grid()
    candidate_summaries: list[CalibrationSummary] = []
    for candidate in candidates:
        summary = evaluate_threshold_candidate(
            samples,
            medium_threshold=candidate.medium_threshold,
            high_threshold=candidate.high_threshold,
            require_election_anchor=require_election_anchor,
        )
        candidate_summaries.append(summary)

    def qualifies(summary: CalibrationSummary) -> bool:
        # Safety posture: do not lower claim-likeness thresholds below baseline
        # during first calibration promotion.
        if summary.candidate.medium_threshold < baseline_medium:
            return False
        if summary.candidate.high_threshold < baseline_high:
            return False
        if summary.benign_fp_rate > (baseline.benign_fp_rate + 0.01):
            return False
        for language, baseline_metrics in baseline.language_metrics.items():
            candidate_metrics = summary.language_metrics.get(language)
            if candidate_metrics is None:
                return False
            if candidate_metrics.f1 < (baseline_metrics.f1 - 0.03):
                return False
        return True

    qualified = [summary for summary in candidate_summaries if qualifies(summary)]
    if not qualified:
        return baseline, baseline, candidate_summaries

    target_medium = (
        round(governance_target_medium, 6)
        if governance_target_medium is not None
        else round(baseline_medium, 6)
    )
    target_high = (
        round(governance_target_high, 6)
        if governance_target_high is not None
        else round(baseline_high, 6)
    )

    selected = sorted(
        qualified,
        key=lambda summary: (
            round(-summary.global_metrics.f1, 12),
            round(summary.benign_fp_rate, 12),
            round(
                abs(summary.candidate.medium_threshold - target_medium)
                + abs(summary.candidate.high_threshold - target_high),
                12,
            ),
            round(
                abs(summary.candidate.medium_threshold - baseline_medium)
                + abs(summary.candidate.high_threshold - baseline_high),
                12,
            ),
        ),
    )[0]
    return baseline, selected, candidate_summaries
