from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

ClaimBand = Literal["low", "medium", "high"]

TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']+")

ELECTION_ANCHOR_TERMS = {
    "election",
    "elections",
    "electoral",
    "vote",
    "votes",
    "voting",
    "ballot",
    "ballots",
    "tally",
    "tallies",
    "results",
    "iebc",
    "poll",
    "polling",
    "constituency",
    "constituencies",
}
ASSERTIVE_CLAIM_TERMS = {
    "is",
    "are",
    "was",
    "were",
    "has",
    "have",
    "will",
    "did",
    "rigged",
    "manipulated",
    "falsified",
    "stolen",
    "fraud",
    "fraudulent",
    "fake",
}
DISINFO_NARRATIVE_TERMS = {
    "rigged",
    "manipulated",
    "falsified",
    "stolen",
    "fake",
    "fraud",
    "fraudulent",
}
HEDGING_TERMS = {
    "alleged",
    "allegedly",
    "rumor",
    "rumour",
    "unconfirmed",
    "possible",
    "possibly",
    "maybe",
    "might",
    "could",
    "seems",
    "seem",
}


@dataclass(frozen=True)
class ClaimLikenessAssessment:
    score: float
    band: ClaimBand
    has_election_anchor: bool
    features: tuple[str, ...]


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("’", "'")
    return normalized.lower().strip()


def _tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(_normalize_text(value))


def contains_election_anchor(text: str) -> bool:
    return bool(set(_tokenize(text)) & ELECTION_ANCHOR_TERMS)


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def assess_claim_likeness(
    text: str,
    *,
    medium_threshold: float,
    high_threshold: float,
) -> ClaimLikenessAssessment:
    tokens = _tokenize(text)
    token_set = set(tokens)
    score = 0.0
    features: list[str] = []

    has_election_anchor = bool(token_set & ELECTION_ANCHOR_TERMS)
    if has_election_anchor:
        score += 0.35
        features.append("election_anchor")

    if token_set & ASSERTIVE_CLAIM_TERMS:
        score += 0.25
        features.append("assertive_claim_term")

    if token_set & DISINFO_NARRATIVE_TERMS:
        score += 0.20
        features.append("disinfo_narrative_term")

    if any(token.isdigit() for token in tokens):
        score += 0.10
        features.append("numeric_reference")

    if len(tokens) >= 8:
        score += 0.10
        features.append("long_form_statement")

    if "?" in text:
        score -= 0.20
        features.append("question_penalty")

    if token_set & HEDGING_TERMS:
        score -= 0.20
        features.append("hedging_penalty")

    score = _clamp_score(score)
    if score >= high_threshold:
        band: ClaimBand = "high"
    elif score >= medium_threshold:
        band = "medium"
    else:
        band = "low"
    return ClaimLikenessAssessment(
        score=score,
        band=band,
        has_election_anchor=has_election_anchor,
        features=tuple(sorted(features)),
    )
