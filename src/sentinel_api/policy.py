from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import cast, get_args

from sentinel_api.logging import get_logger
from sentinel_api.model_artifact_repository import resolve_runtime_model_version
from sentinel_api.model_registry import (
    DEFAULT_MODEL_TIMEOUT_MS,
    get_model_runtime,
    score_claim_with_fallback,
)
from sentinel_core.claim_likeness import contains_election_anchor
from sentinel_core.model_runtime import ClaimBand
from sentinel_core.models import (
    Action,
    EvidenceItem,
    Label,
    LanguageSpan,
    ModerationContext,
    ModerationResponse,
)
from sentinel_core.policy_config import (
    DeploymentStage,
    EffectivePolicyRuntime,
    get_policy_config,
    resolve_policy_runtime,
)
from sentinel_langpack import get_wave1_pack_matchers
from sentinel_langpack.registry import resolve_pack_versions
from sentinel_lexicon.hot_triggers import find_hot_trigger_matches
from sentinel_lexicon.lexicon import get_lexicon_matcher
from sentinel_lexicon.lexicon_repository import LexiconEntry
from sentinel_lexicon.vector_matcher import DEFAULT_VECTOR_MATCH_THRESHOLD, find_vector_match
from sentinel_router.language_router import detect_language_spans

logger = get_logger("sentinel.policy")


@dataclass
class Decision:
    action: Action
    labels: list[Label]
    reason_codes: list[str]
    evidence: list[EvidenceItem]
    toxicity: float


KNOWN_LABELS = set(get_args(Label))


def _as_label(value: str) -> Label:
    if value not in KNOWN_LABELS:
        raise ValueError(f"unknown moderation label: {value}")
    return cast(Label, value)


def _apply_deployment_stage(
    decision: Decision,
    *,
    runtime: EffectivePolicyRuntime,
) -> Decision:
    stage = runtime.effective_deployment_stage
    if stage == DeploymentStage.SUPERVISED:
        return decision
    if stage == DeploymentStage.ADVISORY:
        if decision.action != "BLOCK":
            return decision
        reason_codes = sorted(set(decision.reason_codes + ["R_STAGE_ADVISORY_BLOCK_DOWNGRADED"]))
        return Decision(
            action="REVIEW",
            labels=decision.labels,
            reason_codes=reason_codes,
            evidence=decision.evidence,
            toxicity=runtime.toxicity_by_action.REVIEW,
        )
    if stage == DeploymentStage.SHADOW:
        if decision.action == "ALLOW":
            return decision
        reason_codes = sorted(set(decision.reason_codes + ["R_STAGE_SHADOW_NO_ENFORCE"]))
        return Decision(
            action="ALLOW",
            labels=decision.labels,
            reason_codes=reason_codes,
            evidence=decision.evidence,
            toxicity=runtime.toxicity_by_action.ALLOW,
        )
    return decision


def _band_from_score(score: float, *, medium_threshold: float, high_threshold: float) -> ClaimBand:
    if score >= high_threshold:
        return "high"
    if score >= medium_threshold:
        return "medium"
    return "low"


def detect_language_span(text: str, config=None) -> list[LanguageSpan]:
    config = config or get_policy_config()
    return detect_language_spans(
        text,
        sw_hints=config.language_hints.sw,
        sh_hints=config.language_hints.sh,
        fallback_lang="en",
    )


def _deduplicate_entries(entries: list[LexiconEntry]) -> list[LexiconEntry]:
    seen: set[tuple[str, str, str, str, int, str]] = set()
    deduped: list[LexiconEntry] = []
    for entry in entries:
        key = (
            entry.term,
            entry.action,
            entry.label,
            entry.reason_code,
            entry.severity,
            entry.lang,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _context_threshold_adjustment(
    context: ModerationContext | None,
    *,
    runtime: EffectivePolicyRuntime,
) -> float:
    del runtime
    if context is None:
        return 0.0
    channel = (context.channel or "").strip().lower()
    if channel == "forward":
        return -0.04
    if channel == "broadcast":
        return 0.02
    return 0.0


def _resolved_vector_match_threshold(runtime: EffectivePolicyRuntime) -> float:
    if runtime.vector_match_threshold is not None:
        return runtime.vector_match_threshold
    raw = os.getenv("SENTINEL_VECTOR_MATCH_THRESHOLD")
    if raw is None:
        return DEFAULT_VECTOR_MATCH_THRESHOLD
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_VECTOR_MATCH_THRESHOLD
    if value < 0 or value > 1:
        return DEFAULT_VECTOR_MATCH_THRESHOLD
    return value


def _vector_matching_configured() -> bool:
    database_url = os.getenv("SENTINEL_DATABASE_URL", "").strip()
    if not database_url:
        return False
    raw = os.getenv("SENTINEL_VECTOR_MATCH_ENABLED")
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def evaluate_text(
    text: str,
    matcher=None,
    config=None,
    runtime=None,
    *,
    context: ModerationContext | None = None,
) -> Decision:
    runtime = runtime or resolve_policy_runtime(config=config)
    config = runtime.config
    matcher = matcher or get_lexicon_matcher()
    evidence: list[EvidenceItem] = []
    labels: list[Label] = []
    reason_codes: list[str] = []

    hot_matches = find_hot_trigger_matches(
        text,
        lexicon_version=matcher.version,
        entries=matcher.entries,
    )
    hot_block_matches = [entry for entry in hot_matches if entry.action == "BLOCK"]
    if hot_block_matches:
        block_matches = _deduplicate_entries(hot_block_matches)
        matches = block_matches
    else:
        matcher_matches = matcher.match(text)
        matches = _deduplicate_entries(hot_matches + matcher_matches)
        block_matches = [entry for entry in matches if entry.action == "BLOCK"]

    for entry in block_matches:
        labels.append(_as_label(entry.label))
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
        decision = Decision(
            action="BLOCK",
            labels=sorted(set(labels)),
            reason_codes=sorted(set(reason_codes)),
            evidence=evidence,
            toxicity=runtime.toxicity_by_action.BLOCK,
        )
        return _apply_deployment_stage(decision, runtime=runtime)

    review_matches = [entry for entry in matches if entry.action == "REVIEW"]

    for entry in review_matches:
        labels.append(_as_label(entry.label))
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
        decision = Decision(
            action="REVIEW",
            labels=sorted(set(labels)),
            reason_codes=sorted(set(reason_codes)),
            evidence=evidence,
            toxicity=runtime.toxicity_by_action.REVIEW,
        )
        return _apply_deployment_stage(decision, runtime=runtime)

    pack_matchers = get_wave1_pack_matchers()
    has_pack_matches = False
    for pack_matcher in pack_matchers:
        for entry in pack_matcher.match(text):
            has_pack_matches = True
            labels.append(_as_label(entry.label))
            reason_codes.append(entry.reason_code)
            evidence.append(
                EvidenceItem(
                    type="lexicon",
                    match=entry.term,
                    severity=entry.severity,
                    lang=pack_matcher.language,
                )
            )

    if has_pack_matches:
        decision = Decision(
            action="REVIEW",
            labels=sorted(set(labels)),
            reason_codes=sorted(set(reason_codes)),
            evidence=evidence,
            toxicity=runtime.toxicity_by_action.REVIEW,
        )
        return _apply_deployment_stage(decision, runtime=runtime)

    threshold_delta = _context_threshold_adjustment(context, runtime=runtime)
    if threshold_delta:
        logger.debug(
            "context_threshold_adjustment",
            channel=context.channel if context else None,
            delta=threshold_delta,
        )
    vector_threshold = _resolved_vector_match_threshold(runtime)
    vector_threshold = max(0.0, min(1.0, vector_threshold + threshold_delta))

    vector_match = None
    if _vector_matching_configured():
        model_runtime = get_model_runtime()
        embedding_provider = model_runtime.embedding_provider
        embedding_model = model_runtime.embedding_provider_id
        query_embedding = embedding_provider.embed(text, timeout_ms=DEFAULT_MODEL_TIMEOUT_MS)
        if query_embedding is not None:
            vector_match = find_vector_match(
                text,
                lexicon_version=matcher.version,
                query_embedding=query_embedding,
                embedding_model=embedding_model,
                min_similarity=vector_threshold,
            )
    if vector_match is not None:
        entry = vector_match.entry
        # Safety posture: semantic/vector evidence is advisory and cannot directly
        # escalate to BLOCK without a deterministic lexical hit.
        action = "REVIEW"
        toxicity = runtime.toxicity_by_action.REVIEW
        decision = Decision(
            action=action,
            labels=[_as_label(entry.label)],
            reason_codes=[entry.reason_code],
            evidence=[
                EvidenceItem(
                    type="vector_match",
                    match=entry.term,
                    severity=entry.severity,
                    lang=entry.lang,
                    match_id=vector_match.match_id,
                    similarity=vector_match.similarity,
                )
            ],
            toxicity=toxicity,
        )
        return _apply_deployment_stage(decision, runtime=runtime)

    claim_score = score_claim_with_fallback(text)
    if claim_score is not None:
        claim_score_value, _ = claim_score
    else:
        claim_score_value = 0.0
    if context is not None and (context.source or "").strip().lower() == "partner_factcheck":
        adjusted = min(claim_score_value * 1.10, 1.0)
        logger.debug(
            "context_partner_factcheck_claim_multiplier",
            base=claim_score_value,
            adjusted=adjusted,
        )
        claim_score_value = adjusted
    claim_band = _band_from_score(
        claim_score_value,
        medium_threshold=runtime.claim_likeness.medium_threshold,
        high_threshold=runtime.claim_likeness.high_threshold,
    )
    claim_matches_anchor = (
        contains_election_anchor(text) or not runtime.claim_likeness.require_election_anchor
    )
    if claim_matches_anchor and claim_band in {"medium", "high"}:
        reason_code = (
            "R_DISINFO_CLAIM_LIKENESS_HIGH"
            if claim_band == "high"
            else "R_DISINFO_CLAIM_LIKENESS_MEDIUM"
        )
        decision = Decision(
            action="REVIEW",
            labels=["DISINFO_RISK"],
            reason_codes=[reason_code],
            evidence=[
                EvidenceItem(
                    type="model_span",
                    span=text[:80],
                    confidence=claim_score_value,
                )
            ],
            toxicity=runtime.toxicity_by_action.REVIEW,
        )
        return _apply_deployment_stage(decision, runtime=runtime)

    if runtime.no_match_action == "REVIEW":
        decision = Decision(
            action="REVIEW",
            labels=["DOGWHISTLE_WATCH"],
            reason_codes=["R_DOGWHISTLE_CONTEXT_REQUIRED"],
            evidence=[
                EvidenceItem(
                    type="model_span",
                    span=text[:80],
                    confidence=runtime.allow_confidence,
                )
            ],
            toxicity=runtime.toxicity_by_action.REVIEW,
        )
        return _apply_deployment_stage(decision, runtime=runtime)

    decision = Decision(
        action="ALLOW",
        labels=[_as_label(config.allow_label)],
        reason_codes=[config.allow_reason_code],
        evidence=[
            EvidenceItem(
                type="model_span",
                span=text[:80],
                confidence=runtime.allow_confidence,
            )
        ],
        toxicity=runtime.toxicity_by_action.ALLOW,
    )
    return _apply_deployment_stage(decision, runtime=runtime)


def moderate(
    text: str,
    *,
    context: ModerationContext | None = None,
    runtime: EffectivePolicyRuntime | None = None,
) -> ModerationResponse:
    start = time.perf_counter()
    runtime = runtime or resolve_policy_runtime()
    config = runtime.config
    matcher = get_lexicon_matcher()
    decision = evaluate_text(text, matcher=matcher, config=config, runtime=runtime, context=context)
    latency_ms = int((time.perf_counter() - start) * 1000)
    pack_versions = resolve_pack_versions(config.pack_versions)
    effective_model_version = resolve_runtime_model_version(config.model_version)
    return ModerationResponse(
        toxicity=decision.toxicity,
        labels=decision.labels,
        action=decision.action,
        reason_codes=decision.reason_codes,
        evidence=decision.evidence,
        language_spans=detect_language_span(text, config=config),
        model_version=effective_model_version,
        lexicon_version=matcher.version,
        pack_versions=pack_versions,
        policy_version=runtime.effective_policy_version,
        latency_ms=latency_ms,
    )
