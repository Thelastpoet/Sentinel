from __future__ import annotations

from sentinel_core.claim_likeness import assess_claim_likeness


def test_claim_likeness_high_band_for_assertive_election_claim() -> None:
    assessment = assess_claim_likeness(
        "IEBC results were manipulated and falsified in 12 constituencies.",
        medium_threshold=0.4,
        high_threshold=0.7,
    )
    assert assessment.band == "high"
    assert assessment.has_election_anchor is True
    assert assessment.score >= 0.7


def test_claim_likeness_medium_band_for_hedged_claim() -> None:
    assessment = assess_claim_likeness(
        "Election results were maybe manipulated.",
        medium_threshold=0.4,
        high_threshold=0.7,
    )
    assert assessment.band == "medium"
    assert 0.4 <= assessment.score < 0.7


def test_claim_likeness_low_for_non_claim_text() -> None:
    assessment = assess_claim_likeness(
        "We should discuss policy peacefully.",
        medium_threshold=0.4,
        high_threshold=0.7,
    )
    assert assessment.band == "low"
    assert assessment.score < 0.4


def test_claim_likeness_respects_threshold_overrides() -> None:
    assessment = assess_claim_likeness(
        "Election results were manipulated and falsified.",
        medium_threshold=0.85,
        high_threshold=0.95,
    )
    assert assessment.band == "low"
