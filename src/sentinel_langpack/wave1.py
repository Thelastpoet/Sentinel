from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args

from pydantic import BaseModel, ConfigDict, Field

from sentinel_core.eval_harness import EvalSample, evaluate_samples, load_eval_samples
from sentinel_core.models import Label

PackStage = Literal["advisory", "supervised"]
HIGH_SEVERITY_LABELS = [
    "ETHNIC_CONTEMPT",
    "INCITEMENT_VIOLENCE",
    "HARASSMENT_THREAT",
]
KNOWN_LABELS = set(get_args(Label))
WORD_BOUNDARY_CHARS = r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']"
TERM_TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']+")
PACK_VERSION_PATTERN = re.compile(r"^pack-[a-z0-9-]+-\d+\.\d+$")


class PackNormalization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replacements: dict[str, str] = Field(default_factory=dict)


class PackLexiconEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=128)
    label: str
    action: Literal["REVIEW", "BLOCK"]
    reason_code: str = Field(min_length=1, max_length=64)
    severity: int = Field(ge=1, le=3)


class PackLexicon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[PackLexiconEntry] = Field(min_length=1)


class PackCalibration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_stage: PackStage = "advisory"
    f1_threshold_advisory: float = Field(ge=0, le=1, default=0.80)
    f1_threshold_supervised: float = Field(ge=0, le=1, default=0.86)
    benign_block_fp_rate_max: float = Field(ge=0, le=1, default=0.005)
    benign_block_or_review_fp_rate_max: float = Field(ge=0, le=1, default=0.03)
    max_disparity_ratio: float = Field(ge=0, default=1.5)
    min_eval_samples: int = Field(ge=1, default=1000)
    min_code_switched_ratio: float = Field(ge=0, le=1, default=0.20)
    min_annotators_per_sample: int = Field(ge=1, default=3)
    min_krippendorff_alpha: float = Field(ge=0, le=1, default=0.67)
    required_high_severity_labels: list[str] = Field(
        default_factory=lambda: list(HIGH_SEVERITY_LABELS)
    )

    def required_f1_threshold(self) -> float:
        if self.target_stage == "supervised":
            return self.f1_threshold_supervised
        return self.f1_threshold_advisory


class PackArtifactPaths(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalization: str
    lexicon: str
    calibration: str


class PackAnnotationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotators_per_sample: int = Field(ge=1)
    krippendorff_alpha: float = Field(ge=0, le=1)


class Wave1PackManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(min_length=2, max_length=16)
    pack_version: str = Field(min_length=1, max_length=64)
    priority: int = Field(ge=1)
    directory: str = Field(min_length=1)
    artifacts: PackArtifactPaths
    eval_dataset: str = Field(min_length=1)
    annotation_metadata: PackAnnotationMetadata

    def validate_pack_version(self) -> None:
        if not PACK_VERSION_PATTERN.fullmatch(self.pack_version):
            raise ValueError(
                f"invalid pack_version={self.pack_version!r}; expected pack-<lang>-<major.minor>"
            )


class Wave1PackRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wave: Literal["wave1"] = "wave1"
    packs: list[Wave1PackManifest] = Field(min_length=1)


@dataclass(frozen=True)
class PackGateResult:
    language: str
    pack_version: str
    passed: bool
    gate_failures: list[str]
    sample_count: int
    code_switched_ratio: float
    report: dict[str, Any]


@dataclass(frozen=True)
class _PackDecision:
    action: Literal["ALLOW", "REVIEW", "BLOCK"]
    labels: list[str]


def _normalize_text(text: str, replacements: dict[str, str]) -> str:
    normalized = unicodedata.normalize("NFKC", text).replace("’", "'").lower()
    for source, target in replacements.items():
        source_key = source.strip().lower()
        if not source_key:
            continue
        normalized = normalized.replace(source_key, target.strip().lower())
    return normalized


def _compile_term_pattern(term: str) -> re.Pattern[str]:
    normalized = unicodedata.normalize("NFKC", term).replace("’", "'").lower().strip()
    if not normalized:
        return re.compile(r"(?!x)x")
    tokens = TERM_TOKEN_PATTERN.findall(normalized)
    if not tokens:
        return re.compile(re.escape(normalized))
    boundary_start = rf"(?<!{WORD_BOUNDARY_CHARS})"
    boundary_end = rf"(?!{WORD_BOUNDARY_CHARS})"
    token_pattern = r"[\W_]+".join(re.escape(token) for token in tokens)
    return re.compile(rf"{boundary_start}{token_pattern}{boundary_end}")


def _resolve_path(base_dir: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_pack_artifacts(
    manifest: Wave1PackManifest, *, registry_path: Path
) -> tuple[PackNormalization, PackLexicon, PackCalibration, Path]:
    root = registry_path.parent
    pack_dir = _resolve_path(root, manifest.directory)
    normalization = PackNormalization.model_validate(
        _load_json(_resolve_path(pack_dir, manifest.artifacts.normalization))
    )
    lexicon = PackLexicon.model_validate(
        _load_json(_resolve_path(pack_dir, manifest.artifacts.lexicon))
    )
    calibration = PackCalibration.model_validate(
        _load_json(_resolve_path(pack_dir, manifest.artifacts.calibration))
    )
    return normalization, lexicon, calibration, pack_dir


def load_wave1_registry(
    path: str | Path = "data/langpacks/registry.json",
) -> Wave1PackRegistry:
    registry_path = Path(path).resolve()
    registry = Wave1PackRegistry.model_validate(_load_json(registry_path))
    seen_languages: set[str] = set()
    seen_versions: set[str] = set()
    for manifest in registry.packs:
        manifest.validate_pack_version()
        normalized_lang = manifest.language.strip().lower()
        if normalized_lang in seen_languages:
            raise ValueError(f"duplicate language in wave1 registry: {normalized_lang}")
        if manifest.pack_version in seen_versions:
            raise ValueError(
                f"duplicate pack_version in wave1 registry: {manifest.pack_version}"
            )
        seen_languages.add(normalized_lang)
        seen_versions.add(manifest.pack_version)
    return registry


def wave1_packs_in_priority_order(registry: Wave1PackRegistry) -> list[Wave1PackManifest]:
    return sorted(registry.packs, key=lambda item: item.priority)


def load_pack_eval_samples(
    manifest: Wave1PackManifest, *, registry_path: str | Path = "data/langpacks/registry.json"
) -> list[EvalSample]:
    registry_file = Path(registry_path).resolve()
    eval_path = _resolve_path(registry_file.parent, manifest.eval_dataset)
    return load_eval_samples(eval_path)


def build_pack_moderate_fn(
    manifest: Wave1PackManifest, *, registry_path: str | Path = "data/langpacks/registry.json"
):
    registry_file = Path(registry_path).resolve()
    normalization, lexicon, _calibration, _pack_dir = _load_pack_artifacts(
        manifest, registry_path=registry_file
    )
    compiled_entries = [
        (entry, _compile_term_pattern(entry.term)) for entry in lexicon.entries
    ]

    def _moderate(text: str) -> _PackDecision:
        normalized = _normalize_text(text, normalization.replacements)
        block_labels: list[str] = []
        review_labels: list[str] = []
        for entry, pattern in compiled_entries:
            if not pattern.search(normalized):
                continue
            if entry.label not in KNOWN_LABELS:
                continue
            if entry.action == "BLOCK":
                block_labels.append(entry.label)
            else:
                review_labels.append(entry.label)
        if block_labels:
            return _PackDecision(action="BLOCK", labels=sorted(set(block_labels)))
        if review_labels:
            return _PackDecision(action="REVIEW", labels=sorted(set(review_labels)))
        return _PackDecision(action="ALLOW", labels=["BENIGN_POLITICAL_SPEECH"])

    return _moderate


def evaluate_pack_gates(
    manifest: Wave1PackManifest, *, registry_path: str | Path = "data/langpacks/registry.json"
) -> PackGateResult:
    registry_file = Path(registry_path).resolve()
    normalization, lexicon, calibration, _pack_dir = _load_pack_artifacts(
        manifest, registry_path=registry_file
    )
    del normalization, lexicon
    samples = load_pack_eval_samples(manifest, registry_path=registry_file)
    moderate_fn = build_pack_moderate_fn(manifest, registry_path=registry_file)
    report = evaluate_samples(samples, moderate_fn=moderate_fn)

    sample_count = len(samples)
    code_switched_count = sum(1 for sample in samples if sample.is_code_switched)
    code_switched_ratio = (
        float(code_switched_count) / float(sample_count) if sample_count else 0.0
    )
    failures: list[str] = []

    if sample_count < calibration.min_eval_samples:
        failures.append(
            f"sample_count={sample_count} < min_eval_samples={calibration.min_eval_samples}"
        )
    if code_switched_ratio < calibration.min_code_switched_ratio:
        failures.append(
            "code_switched_ratio="
            f"{code_switched_ratio:.4f} < min_code_switched_ratio={calibration.min_code_switched_ratio:.4f}"
        )

    annotation = manifest.annotation_metadata
    if annotation.annotators_per_sample < calibration.min_annotators_per_sample:
        failures.append(
            "annotators_per_sample="
            f"{annotation.annotators_per_sample} < min_annotators_per_sample={calibration.min_annotators_per_sample}"
        )
    if annotation.krippendorff_alpha < calibration.min_krippendorff_alpha:
        failures.append(
            "krippendorff_alpha="
            f"{annotation.krippendorff_alpha:.4f} < min_krippendorff_alpha={calibration.min_krippendorff_alpha:.4f}"
        )

    required_f1 = calibration.required_f1_threshold()
    global_metrics = report["global_harm_label_metrics"]
    for label in calibration.required_high_severity_labels:
        metrics = global_metrics.get(label)
        if metrics is None:
            failures.append(f"missing harm metrics for label={label}")
            continue
        support = float(metrics["support"])
        if support <= 0:
            failures.append(f"label={label} has zero support in eval dataset")
            continue
        if float(metrics["f1"]) < required_f1:
            failures.append(
                f"label={label} f1={float(metrics['f1']):.4f} < required={required_f1:.4f}"
            )

    benign_metrics = report["benign_false_positive_metrics"]
    block_fp_rate = float(benign_metrics["block_fp_rate"])
    block_or_review_fp_rate = float(benign_metrics["block_or_review_fp_rate"])
    if block_fp_rate > calibration.benign_block_fp_rate_max:
        failures.append(
            "block_fp_rate="
            f"{block_fp_rate:.4f} > benign_block_fp_rate_max={calibration.benign_block_fp_rate_max:.4f}"
        )
    if block_or_review_fp_rate > calibration.benign_block_or_review_fp_rate_max:
        failures.append(
            "block_or_review_fp_rate="
            f"{block_or_review_fp_rate:.4f} > benign_block_or_review_fp_rate_max={calibration.benign_block_or_review_fp_rate_max:.4f}"
        )

    disparity_ratio = float(report["subgroup_disparity_metrics"]["max_disparity_ratio"])
    if disparity_ratio > calibration.max_disparity_ratio:
        failures.append(
            "max_disparity_ratio="
            f"{disparity_ratio:.4f} > max_disparity_ratio={calibration.max_disparity_ratio:.4f}"
        )

    return PackGateResult(
        language=manifest.language,
        pack_version=manifest.pack_version,
        passed=not failures,
        gate_failures=failures,
        sample_count=sample_count,
        code_switched_ratio=round(code_switched_ratio, 6),
        report=report,
    )

