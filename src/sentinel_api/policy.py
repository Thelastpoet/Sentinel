from __future__ import annotations

import time
from dataclasses import dataclass

from sentinel_api.language_router import detect_language_spans
from sentinel_api.lexicon import get_lexicon_matcher
from sentinel_api.models import EvidenceItem, LanguageSpan, ModerationResponse
from sentinel_api.policy_config import get_policy_config


@dataclass
class Decision:
    action: str
    labels: list[str]
    reason_codes: list[str]
    evidence: list[EvidenceItem]
    toxicity: float


def detect_language_span(text: str, config=None) -> list[LanguageSpan]:
    config = config or get_policy_config()
    return detect_language_spans(
        text,
        sw_hints=config.language_hints.sw,
        sh_hints=config.language_hints.sh,
        fallback_lang="en",
    )


def evaluate_text(text: str, matcher=None, config=None) -> Decision:
    config = config or get_policy_config()
    matcher = matcher or get_lexicon_matcher()
    evidence: list[EvidenceItem] = []
    labels: list[str] = []
    reason_codes: list[str] = []

    matches = matcher.match(text)
    block_matches = [entry for entry in matches if entry.action == "BLOCK"]
    review_matches = [entry for entry in matches if entry.action == "REVIEW"]

    for entry in block_matches:
        labels.append(entry.label)
        reason_codes.append(entry.reason_code)
        evidence.append(
            EvidenceItem(
                type="lexicon",
                match=entry.term,
                severity=entry.severity,
                lang=entry.lang,
            )
        )

    if block_matches:
        return Decision(
            action="BLOCK",
            labels=sorted(set(labels)),
            reason_codes=sorted(set(reason_codes)),
            evidence=evidence,
            toxicity=config.toxicity_by_action.BLOCK,
        )

    for entry in review_matches:
        labels.append(entry.label)
        reason_codes.append(entry.reason_code)
        evidence.append(
            EvidenceItem(
                type="lexicon",
                match=entry.term,
                severity=entry.severity,
                lang=entry.lang,
            )
        )

    if review_matches:
        return Decision(
            action="REVIEW",
            labels=sorted(set(labels)),
            reason_codes=sorted(set(reason_codes)),
            evidence=evidence,
            toxicity=config.toxicity_by_action.REVIEW,
        )

    return Decision(
        action="ALLOW",
        labels=[config.allow_label],
        reason_codes=[config.allow_reason_code],
        evidence=[
            EvidenceItem(
                type="model_span",
                span=text[:80],
                confidence=config.allow_confidence,
            )
        ],
        toxicity=config.toxicity_by_action.ALLOW,
    )


def moderate(text: str) -> ModerationResponse:
    start = time.perf_counter()
    config = get_policy_config()
    matcher = get_lexicon_matcher()
    decision = evaluate_text(text, matcher=matcher, config=config)
    latency_ms = int((time.perf_counter() - start) * 1000)
    return ModerationResponse(
        toxicity=decision.toxicity,
        labels=decision.labels,
        action=decision.action,
        reason_codes=decision.reason_codes,
        evidence=decision.evidence,
        language_spans=detect_language_span(text, config=config),
        model_version=config.model_version,
        lexicon_version=matcher.version,
        pack_versions=config.pack_versions,
        policy_version=config.version,
        latency_ms=latency_ms,
    )
