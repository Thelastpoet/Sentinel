from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, get_args

from sentinel_core.models import Label

KNOWN_LABELS = set(get_args(Label))
HARM_LABELS = sorted(label for label in KNOWN_LABELS if label != "BENIGN_POLITICAL_SPEECH")


@dataclass(frozen=True)
class EvalSample:
    sample_id: str
    text: str
    language: str
    labels: list[str]
    is_benign_political: bool
    is_code_switched: bool = False
    subgroup: str | None = None


class ModerationDecisionLike(Protocol):
    @property
    def action(self) -> str: ...

    @property
    def labels(self) -> Sequence[str]: ...


def _as_non_empty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _as_labels(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("labels must be a non-empty list")
    labels: list[str] = []
    for item in value:
        label = _as_non_empty_string(item, field_name="label")
        if label not in KNOWN_LABELS:
            raise ValueError(f"unknown label: {label}")
        labels.append(label)
    return sorted(set(labels))


def _parse_sample(record: dict[str, Any], *, line_number: int) -> EvalSample:
    sample_id = record.get("id")
    if sample_id is None:
        sample_id = f"sample-{line_number}"
    sample_id = _as_non_empty_string(sample_id, field_name="id")
    text = _as_non_empty_string(record.get("text"), field_name="text")
    language = _as_non_empty_string(record.get("language"), field_name="language").lower()
    labels = _as_labels(record.get("labels"))
    raw_benign = record.get("is_benign_political")
    if raw_benign is None:
        is_benign_political = "BENIGN_POLITICAL_SPEECH" in labels
    elif isinstance(raw_benign, bool):
        is_benign_political = raw_benign
    else:
        raise ValueError("is_benign_political must be a boolean when provided")
    raw_code_switched = record.get("is_code_switched")
    if raw_code_switched is None:
        is_code_switched = False
    elif isinstance(raw_code_switched, bool):
        is_code_switched = raw_code_switched
    else:
        raise ValueError("is_code_switched must be a boolean when provided")
    subgroup = record.get("subgroup")
    if subgroup is None:
        subgroup_value: str | None = None
    else:
        subgroup_value = _as_non_empty_string(subgroup, field_name="subgroup")
    return EvalSample(
        sample_id=sample_id,
        text=text,
        language=language,
        labels=labels,
        is_benign_political=is_benign_political,
        is_code_switched=is_code_switched,
        subgroup=subgroup_value,
    )


def load_eval_samples(path: str | Path) -> list[EvalSample]:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(path_obj)
    samples: list[EvalSample] = []
    for index, raw_line in enumerate(path_obj.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at line {index}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"line {index} must be a JSON object")
        samples.append(_parse_sample(payload, line_number=index))
    if not samples:
        raise ValueError("evaluation file has no samples")
    return samples


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _score_counts(counts: dict[str, int]) -> dict[str, float]:
    tp = counts.get("tp", 0)
    fp = counts.get("fp", 0)
    fn = counts.get("fn", 0)
    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    f1 = _safe_ratio(2 * precision * recall, precision + recall)
    return {
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "support": float(tp + fn),
    }


def _summarize_label_counts(
    counts_by_label: dict[str, dict[str, int]],
) -> dict[str, dict[str, float]]:
    return {label: _score_counts(counts_by_label[label]) for label in HARM_LABELS}


def evaluate_samples(
    samples: list[EvalSample],
    moderate_fn: Callable[[str], ModerationDecisionLike],
) -> dict[str, Any]:
    if not samples:
        raise ValueError("samples must not be empty")

    global_counts: dict[str, dict[str, int]] = {
        label: {"tp": 0, "fp": 0, "fn": 0} for label in HARM_LABELS
    }
    language_counts: dict[str, dict[str, dict[str, int]]] = {}
    language_sample_counts: dict[str, int] = {}

    benign_total = 0
    benign_block = 0
    benign_block_or_review = 0
    subgroup_counts: dict[str, dict[str, int]] = {}

    for sample in samples:
        response = moderate_fn(sample.text)
        expected_harm = {label for label in sample.labels if label in HARM_LABELS}
        predicted_harm = {label for label in response.labels if label in HARM_LABELS}

        language_sample_counts[sample.language] = language_sample_counts.get(sample.language, 0) + 1
        if sample.language not in language_counts:
            language_counts[sample.language] = {
                label: {"tp": 0, "fp": 0, "fn": 0} for label in HARM_LABELS
            }

        for label in HARM_LABELS:
            if label in predicted_harm and label in expected_harm:
                global_counts[label]["tp"] += 1
                language_counts[sample.language][label]["tp"] += 1
            elif label in predicted_harm and label not in expected_harm:
                global_counts[label]["fp"] += 1
                language_counts[sample.language][label]["fp"] += 1
            elif label not in predicted_harm and label in expected_harm:
                global_counts[label]["fn"] += 1
                language_counts[sample.language][label]["fn"] += 1

        if sample.is_benign_political:
            benign_total += 1
            subgroup_key = sample.subgroup or "unspecified"
            subgroup = subgroup_counts.setdefault(
                subgroup_key,
                {"total": 0, "block": 0, "block_or_review": 0},
            )
            subgroup["total"] += 1

            if response.action == "BLOCK":
                benign_block += 1
                subgroup["block"] += 1
            if response.action in {"BLOCK", "REVIEW"}:
                benign_block_or_review += 1
                subgroup["block_or_review"] += 1

    benign_block_fp_rate = _safe_ratio(benign_block, benign_total)
    benign_block_or_review_fp_rate = _safe_ratio(benign_block_or_review, benign_total)

    subgroup_rates: dict[str, dict[str, float]] = {}
    max_disparity_ratio = 0.0
    max_disparity_group: str | None = None
    for subgroup_name in sorted(subgroup_counts):
        counts = subgroup_counts[subgroup_name]
        subgroup_block_rate = _safe_ratio(counts["block"], counts["total"])
        subgroup_block_or_review_rate = _safe_ratio(counts["block_or_review"], counts["total"])
        if benign_block_or_review_fp_rate > 0:
            disparity_ratio = subgroup_block_or_review_rate / benign_block_or_review_fp_rate
        else:
            disparity_ratio = 0.0
        if disparity_ratio > max_disparity_ratio:
            max_disparity_ratio = disparity_ratio
            max_disparity_group = subgroup_name
        subgroup_rates[subgroup_name] = {
            "sample_count": float(counts["total"]),
            "block_fp_rate": round(subgroup_block_rate, 6),
            "block_or_review_fp_rate": round(subgroup_block_or_review_rate, 6),
            "disparity_ratio_vs_global_benign_block_or_review_fp": round(disparity_ratio, 6),
        }

    language_report: dict[str, Any] = {}
    for language in sorted(language_counts):
        language_report[language] = {
            "sample_count": float(language_sample_counts.get(language, 0)),
            "harm_label_metrics": _summarize_label_counts(language_counts[language]),
        }

    return {
        "sample_count": float(len(samples)),
        "harm_labels": HARM_LABELS,
        "global_harm_label_metrics": _summarize_label_counts(global_counts),
        "language_harm_label_metrics": language_report,
        "benign_false_positive_metrics": {
            "sample_count": float(benign_total),
            "block_fp_rate": round(benign_block_fp_rate, 6),
            "block_or_review_fp_rate": round(benign_block_or_review_fp_rate, 6),
        },
        "subgroup_disparity_metrics": {
            "reference_metric": "benign_block_or_review_fp_rate",
            "max_disparity_ratio": round(max_disparity_ratio, 6),
            "max_disparity_group": max_disparity_group,
            "groups": subgroup_rates,
        },
    }
