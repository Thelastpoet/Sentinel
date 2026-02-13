from __future__ import annotations

import hashlib
import json
import math
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sentinel_core.eval_harness import EvalSample, load_eval_samples
from sentinel_core.models import Label
from sentinel_lexicon.vector_matcher import VECTOR_DIMENSION
from sentinel_lexicon.vector_matcher import embed_text as embed_hash_bow_v1

TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']+")
HARM_LABELS = {
    "ETHNIC_CONTEMPT",
    "INCITEMENT_VIOLENCE",
    "HARASSMENT_THREAT",
    "DOGWHISTLE_WATCH",
    "DISINFO_RISK",
}


@dataclass(frozen=True)
class BakeoffCandidate:
    candidate_id: str
    display_name: str
    embedding_dim: int
    is_baseline: bool
    is_substitute: bool
    unavailable_reason: str | None = None

    @property
    def available(self) -> bool:
        return self.unavailable_reason is None


@dataclass(frozen=True)
class RetrievalLexiconEntry:
    term: str
    label: Label


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("’", "'")
    return normalized.lower().strip()


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(_normalize_text(text))


def _hash_projection(features: list[tuple[str, float]], *, dimension: int) -> list[float]:
    if not features:
        return [0.0] * dimension
    vector = [0.0] * dimension
    for feature, weight in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=16).digest()
        index = int.from_bytes(digest[0:2], byteorder="big") % dimension
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return [0.0] * dimension
    return [value / norm for value in vector]


def _embed_hash_token_v1(text: str) -> list[float]:
    features = [(f"tok:{token}", 1.0) for token in _tokenize(text)]
    return _hash_projection(features, dimension=VECTOR_DIMENSION)


def _embed_hash_chargram_v1(text: str) -> list[float]:
    compact = "".join(_tokenize(text))
    if len(compact) < 3:
        return [0.0] * VECTOR_DIMENSION
    features: list[tuple[str, float]] = []
    for width in (3, 4, 5):
        for idx in range(0, max(0, len(compact) - width + 1)):
            gram = compact[idx : idx + width]
            features.append((f"c{width}:{gram}", 1.0))
    return _hash_projection(features, dimension=VECTOR_DIMENSION)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not any(a) or not any(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True))


def _first_harm_label(sample: EvalSample) -> str:
    for label in sample.labels:
        if label in HARM_LABELS:
            return label
    return "BENIGN_POLITICAL_SPEECH"


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _f1(tp: int, fp: int, fn: int) -> float:
    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    return _safe_ratio(2 * precision * recall, precision + recall)


def load_retrieval_lexicon(path: str | Path) -> list[RetrievalLexiconEntry]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries: list[RetrievalLexiconEntry] = []
    for raw in payload.get("entries", []):
        status = str(raw.get("status", "active")).strip().lower()
        if status != "active":
            continue
        label = str(raw.get("label", "")).strip()
        if label not in HARM_LABELS:
            continue
        term = str(raw.get("term", "")).strip()
        if not term:
            continue
        entries.append(RetrievalLexiconEntry(term=term, label=cast(Label, label)))
    if not entries:
        raise ValueError("no active harm lexicon entries available for bakeoff")
    return entries


def _build_candidates(*, enable_optional_models: bool) -> list[BakeoffCandidate]:
    optional_reason = (
        None if enable_optional_models else "disabled (enable --enable-optional-models)"
    )
    return [
        BakeoffCandidate(
            candidate_id="hash-bow-v1",
            display_name="Hash BOW v1 (baseline)",
            embedding_dim=VECTOR_DIMENSION,
            is_baseline=True,
            is_substitute=False,
        ),
        BakeoffCandidate(
            candidate_id="e5-multilingual-small",
            display_name="multilingual-e5-small",
            embedding_dim=VECTOR_DIMENSION,
            is_baseline=False,
            is_substitute=False,
            unavailable_reason=optional_reason,
        ),
        BakeoffCandidate(
            candidate_id="labse",
            display_name="LaBSE",
            embedding_dim=VECTOR_DIMENSION,
            is_baseline=False,
            is_substitute=False,
            unavailable_reason=optional_reason,
        ),
        BakeoffCandidate(
            candidate_id="hash-token-v1",
            display_name="Hash Token v1 (substitute)",
            embedding_dim=VECTOR_DIMENSION,
            is_baseline=False,
            is_substitute=True,
        ),
        BakeoffCandidate(
            candidate_id="hash-chargram-v1",
            display_name="Hash Chargram v1 (substitute)",
            embedding_dim=VECTOR_DIMENSION,
            is_baseline=False,
            is_substitute=True,
        ),
    ]


def _embed(candidate_id: str, text: str) -> list[float]:
    if candidate_id == "hash-bow-v1":
        return embed_hash_bow_v1(text)
    if candidate_id == "hash-token-v1":
        return _embed_hash_token_v1(text)
    if candidate_id == "hash-chargram-v1":
        return _embed_hash_chargram_v1(text)
    raise ValueError(f"candidate embedding not implemented locally: {candidate_id}")


def _select_candidate_report(
    reports: list[dict[str, Any]],
    *,
    baseline: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    baseline_f1 = float(baseline["weighted_f1"])
    baseline_p95 = float(baseline["p95_ms"])
    baseline_benign_fp = float(baseline["benign_fp_rate"])
    qualified: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []

    for report in reports:
        if bool(report["is_baseline"]):
            continue
        if not bool(report["available"]):
            continue
        report_f1 = float(report["weighted_f1"])
        report_p95 = float(report["p95_ms"])
        report_benign_fp = float(report["benign_fp_rate"])
        quality_improved = report_f1 >= baseline_f1 * 1.05
        latency_win = report_f1 >= baseline_f1 * 0.99 and report_p95 <= baseline_p95 * 0.8
        safety_ok = report_benign_fp <= baseline_benign_fp + 0.01
        qualifies = safety_ok and (quality_improved or latency_win)
        assessments.append(
            {
                "candidate_id": report["candidate_id"],
                "qualifies": qualifies,
                "quality_improved": quality_improved,
                "latency_win": latency_win,
                "safety_ok": safety_ok,
            }
        )
        if qualifies:
            qualified.append(report)

    if qualified:
        qualified.sort(
            key=lambda item: (float(item["weighted_f1"]), -float(item["p95_ms"])), reverse=True
        )
        return str(qualified[0]["candidate_id"]), assessments
    return str(baseline["candidate_id"]), assessments


def run_embedding_bakeoff(
    *,
    input_path: str | Path,
    lexicon_path: str | Path,
    similarity_threshold: float,
    enable_optional_models: bool,
) -> dict[str, Any]:
    if similarity_threshold < 0 or similarity_threshold > 1:
        raise ValueError("similarity_threshold must be within [0,1]")
    samples = load_eval_samples(input_path)
    lexicon_entries = load_retrieval_lexicon(lexicon_path)
    candidates = _build_candidates(enable_optional_models=enable_optional_models)

    reports: list[dict[str, Any]] = []
    for candidate in candidates:
        if not candidate.available:
            reports.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "display_name": candidate.display_name,
                    "available": False,
                    "is_baseline": candidate.is_baseline,
                    "is_substitute": candidate.is_substitute,
                    "unavailable_reason": candidate.unavailable_reason,
                }
            )
            continue

        lexicon_embeddings = {
            item.term: _embed(candidate.candidate_id, item.term) for item in lexicon_entries
        }
        per_label_counts: dict[str, dict[str, int]] = {
            label: {"tp": 0, "fp": 0, "fn": 0} for label in sorted(HARM_LABELS)
        }
        support: dict[str, int] = {label: 0 for label in sorted(HARM_LABELS)}
        benign_total = 0
        benign_fp = 0
        latencies_ms: list[float] = []

        for sample in samples:
            start = time.perf_counter()
            query_vector = _embed(candidate.candidate_id, sample.text)
            best_term = None
            best_label = "BENIGN_POLITICAL_SPEECH"
            best_similarity = -1.0
            for entry in lexicon_entries:
                score = _cosine_similarity(query_vector, lexicon_embeddings[entry.term])
                if score > best_similarity:
                    best_similarity = score
                    best_term = entry.term
                    best_label = entry.label
            latencies_ms.append((time.perf_counter() - start) * 1000)
            predicted = (
                best_label if best_similarity >= similarity_threshold else "BENIGN_POLITICAL_SPEECH"
            )
            expected = _first_harm_label(sample)

            if expected == "BENIGN_POLITICAL_SPEECH":
                benign_total += 1
                if predicted in HARM_LABELS:
                    benign_fp += 1
            else:
                support[expected] += 1
                if predicted == expected:
                    per_label_counts[expected]["tp"] += 1
                else:
                    per_label_counts[expected]["fn"] += 1
                    if predicted in HARM_LABELS:
                        per_label_counts[predicted]["fp"] += 1

            _ = best_term  # explicit for readability in future detailed reporting extensions

        weighted_f1_num = 0.0
        weighted_f1_den = 0
        per_label_f1: dict[str, float] = {}
        for label in sorted(HARM_LABELS):
            counts = per_label_counts[label]
            score = _f1(counts["tp"], counts["fp"], counts["fn"])
            per_label_f1[label] = round(score, 6)
            weighted_f1_num += score * support[label]
            weighted_f1_den += support[label]
        weighted_f1 = _safe_ratio(weighted_f1_num, weighted_f1_den)
        latencies_sorted = sorted(latencies_ms)
        p95_idx = max(0, math.ceil(len(latencies_sorted) * 0.95) - 1)
        p95_ms = latencies_sorted[p95_idx]
        report = {
            "candidate_id": candidate.candidate_id,
            "display_name": candidate.display_name,
            "available": True,
            "is_baseline": candidate.is_baseline,
            "is_substitute": candidate.is_substitute,
            "embedding_dim": candidate.embedding_dim,
            "sample_count": len(samples),
            "weighted_f1": round(weighted_f1, 6),
            "per_label_f1": per_label_f1,
            "benign_fp_rate": round(_safe_ratio(benign_fp, benign_total), 6),
            "mean_ms": round(sum(latencies_ms) / len(latencies_ms), 6),
            "p95_ms": round(p95_ms, 6),
            "max_ms": round(max(latencies_ms), 6),
            "similarity_threshold": similarity_threshold,
        }
        reports.append(report)

    available_reports = [report for report in reports if bool(report.get("available"))]
    baseline_report = next(
        (report for report in available_reports if bool(report.get("is_baseline"))),
        None,
    )
    if baseline_report is None:
        raise ValueError("baseline candidate report is missing")
    selected_candidate_id, gate_assessments = _select_candidate_report(
        available_reports,
        baseline=baseline_report,
    )
    return {
        "input_path": str(input_path),
        "lexicon_path": str(lexicon_path),
        "sample_count": len(samples),
        "similarity_threshold": similarity_threshold,
        "reports": reports,
        "selected_candidate_id": selected_candidate_id,
        "selection_gate_assessments": gate_assessments,
    }
