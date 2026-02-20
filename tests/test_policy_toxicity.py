from __future__ import annotations

from types import SimpleNamespace

from sentinel_api.policy import Decision, _derive_toxicity
from sentinel_core.models import EvidenceItem


def test_toxicity_blended_with_model_confidence() -> None:
    runtime = SimpleNamespace(
        toxicity_by_action=SimpleNamespace(BLOCK=0.9, REVIEW=0.45, ALLOW=0.05)
    )
    decision = Decision(
        action="REVIEW",
        labels=[],
        reason_codes=[],
        evidence=[EvidenceItem(type="model_span", span="...", confidence=0.9)],
        toxicity=0.45,
    )
    assert _derive_toxicity(decision, runtime=runtime) == 0.63


def test_toxicity_unchanged_without_model_evidence() -> None:
    runtime = SimpleNamespace(
        toxicity_by_action=SimpleNamespace(BLOCK=0.9, REVIEW=0.45, ALLOW=0.05)
    )
    decision = Decision(
        action="REVIEW",
        labels=[],
        reason_codes=[],
        evidence=[EvidenceItem(type="lexicon", match="foo", severity=2, lang="en")],
        toxicity=0.45,
    )
    assert _derive_toxicity(decision, runtime=runtime) == 0.45


def test_toxicity_uses_max_confidence_when_multiple_model_spans() -> None:
    runtime = SimpleNamespace(
        toxicity_by_action=SimpleNamespace(BLOCK=0.9, REVIEW=0.45, ALLOW=0.05)
    )
    decision = Decision(
        action="REVIEW",
        labels=[],
        reason_codes=[],
        evidence=[
            EvidenceItem(type="model_span", span="...", confidence=0.2),
            EvidenceItem(type="model_span", span="...", confidence=0.8),
        ],
        toxicity=0.45,
    )
    assert _derive_toxicity(decision, runtime=runtime) == 0.59


def test_toxicity_stays_in_0_1_range() -> None:
    runtime = SimpleNamespace(toxicity_by_action=SimpleNamespace(BLOCK=1.0, REVIEW=1.0, ALLOW=0.0))
    decision = Decision(
        action="BLOCK",
        labels=[],
        reason_codes=[],
        evidence=[EvidenceItem(type="model_span", span="...", confidence=1.0)],
        toxicity=1.0,
    )
    assert _derive_toxicity(decision, runtime=runtime) == 1.0
