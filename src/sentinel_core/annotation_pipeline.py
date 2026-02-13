from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_args

from sentinel_core.models import Label

KNOWN_LABELS = set(get_args(Label))
HARM_LABELS = sorted(label for label in KNOWN_LABELS if label != "BENIGN_POLITICAL_SPEECH")
TIER1_LANGUAGES = ("en", "sw", "sh")


@dataclass(frozen=True)
class AnnotationSample:
    sample_id: str
    text: str
    language: str
    labels: list[str]
    is_benign_political: bool
    subgroup: str | None
    source: str
    annotation_guide_version: str
    qa_status: str


@dataclass(frozen=True)
class DoubleAnnotationSample:
    sample_id: str
    language: str
    annotator_a_labels: list[str]
    annotator_b_labels: list[str]
    adjudicated_labels: list[str]


def _as_non_empty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _as_labels(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list")
    labels: list[str] = []
    for item in value:
        label = _as_non_empty_string(item, field_name=f"{field_name} item")
        if label not in KNOWN_LABELS:
            raise ValueError(f"unknown label in {field_name}: {label}")
        labels.append(label)
    return sorted(set(labels))


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(path_obj)
    rows: list[dict[str, Any]] = []
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
        rows.append(payload)
    if not rows:
        raise ValueError(f"{path_obj} has no records")
    return rows


def load_annotation_samples(path: str | Path) -> list[AnnotationSample]:
    rows = _read_jsonl(path)
    samples: list[AnnotationSample] = []
    for index, row in enumerate(rows, start=1):
        sample_id = _as_non_empty_string(row.get("id"), field_name=f"id@line{index}")
        text = _as_non_empty_string(row.get("text"), field_name=f"text@line{index}")
        language = _as_non_empty_string(
            row.get("language"),
            field_name=f"language@line{index}",
        ).lower()
        labels = _as_labels(row.get("labels"), field_name=f"labels@line{index}")
        raw_benign = row.get("is_benign_political")
        if not isinstance(raw_benign, bool):
            raise ValueError(f"is_benign_political@line{index} must be boolean")
        subgroup_raw = row.get("subgroup")
        subgroup: str | None
        if subgroup_raw is None:
            subgroup = None
        else:
            subgroup = _as_non_empty_string(subgroup_raw, field_name=f"subgroup@line{index}")
        source = _as_non_empty_string(row.get("source"), field_name=f"source@line{index}")
        guide_version = _as_non_empty_string(
            row.get("annotation_guide_version"),
            field_name=f"annotation_guide_version@line{index}",
        )
        qa_status = _as_non_empty_string(row.get("qa_status"), field_name=f"qa_status@line{index}")
        samples.append(
            AnnotationSample(
                sample_id=sample_id,
                text=text,
                language=language,
                labels=labels,
                is_benign_political=raw_benign,
                subgroup=subgroup,
                source=source,
                annotation_guide_version=guide_version,
                qa_status=qa_status,
            )
        )
    return samples


def summarize_annotation_corpus(
    samples: list[AnnotationSample],
    *,
    min_samples: int = 2000,
    required_languages: tuple[str, ...] = TIER1_LANGUAGES,
) -> dict[str, object]:
    if not samples:
        raise ValueError("samples must not be empty")
    language_counts = Counter(sample.language for sample in samples)
    label_counts: Counter[str] = Counter()
    benign_count = 0
    for sample in samples:
        for label in sample.labels:
            label_counts[label] += 1
        if sample.is_benign_political:
            benign_count += 1
    missing_languages = sorted(
        language for language in required_languages if language not in language_counts
    )
    return {
        "sample_count": len(samples),
        "language_counts": dict(sorted(language_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "benign_sample_count": benign_count,
        "tier1_coverage_complete": len(missing_languages) == 0,
        "missing_required_languages": missing_languages,
        "meets_minimum_sample_count": len(samples) >= min_samples,
    }


def load_double_annotation_samples(path: str | Path) -> list[DoubleAnnotationSample]:
    rows = _read_jsonl(path)
    samples: list[DoubleAnnotationSample] = []
    for index, row in enumerate(rows, start=1):
        sample_id = _as_non_empty_string(row.get("id"), field_name=f"id@line{index}")
        language = _as_non_empty_string(
            row.get("language"),
            field_name=f"language@line{index}",
        ).lower()
        labels_a = _as_labels(
            row.get("annotator_a_labels"),
            field_name=f"annotator_a_labels@line{index}",
        )
        labels_b = _as_labels(
            row.get("annotator_b_labels"),
            field_name=f"annotator_b_labels@line{index}",
        )
        adjudicated = _as_labels(
            row.get("adjudicated_labels"),
            field_name=f"adjudicated_labels@line{index}",
        )
        samples.append(
            DoubleAnnotationSample(
                sample_id=sample_id,
                language=language,
                annotator_a_labels=labels_a,
                annotator_b_labels=labels_b,
                adjudicated_labels=adjudicated,
            )
        )
    return samples


def _cohen_kappa_binary(annotator_a: list[bool], annotator_b: list[bool]) -> float:
    if len(annotator_a) != len(annotator_b):
        raise ValueError("annotator lists must have equal length")
    if not annotator_a:
        return 0.0
    total = len(annotator_a)
    agree = sum(1 for a, b in zip(annotator_a, annotator_b, strict=True) if a == b)
    p_observed = agree / total

    p_a_true = sum(1 for value in annotator_a if value) / total
    p_b_true = sum(1 for value in annotator_b if value) / total
    p_a_false = 1.0 - p_a_true
    p_b_false = 1.0 - p_b_true
    p_expected = (p_a_true * p_b_true) + (p_a_false * p_b_false)
    if p_expected >= 1.0:
        return 1.0
    return (p_observed - p_expected) / (1.0 - p_expected)


def summarize_inter_annotator_agreement(
    samples: list[DoubleAnnotationSample],
) -> dict[str, object]:
    if not samples:
        raise ValueError("samples must not be empty")
    exact_match_count = sum(
        1 for sample in samples if set(sample.annotator_a_labels) == set(sample.annotator_b_labels)
    )

    def is_harmful(labels: list[str]) -> bool:
        return any(label in HARM_LABELS for label in labels)

    harmful_a = [is_harmful(sample.annotator_a_labels) for sample in samples]
    harmful_b = [is_harmful(sample.annotator_b_labels) for sample in samples]
    harmful_kappa = _cohen_kappa_binary(harmful_a, harmful_b)

    per_label_kappa: dict[str, float] = {}
    for label in sorted(KNOWN_LABELS):
        binary_a = [label in sample.annotator_a_labels for sample in samples]
        binary_b = [label in sample.annotator_b_labels for sample in samples]
        per_label_kappa[label] = round(_cohen_kappa_binary(binary_a, binary_b), 6)

    return {
        "sample_count": len(samples),
        "exact_label_set_match_rate": round(exact_match_count / len(samples), 6),
        "binary_harmful_kappa": round(harmful_kappa, 6),
        "per_label_kappa": per_label_kappa,
    }
