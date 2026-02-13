from __future__ import annotations

import json

import pytest

import sentinel_api.policy as policy
from sentinel_api.lexicon_repository import LexiconEntry
from sentinel_api.policy_config import get_policy_config, reset_policy_config_cache


def setup_function() -> None:
    reset_policy_config_cache()


def teardown_function() -> None:
    reset_policy_config_cache()


def _matcher() -> object:
    class _Matcher:
        version = "hatelex-v2.1"
        entries: list[LexiconEntry] = []

        def match(self, _text: str) -> list[LexiconEntry]:
            return []

    return _Matcher()


def test_claim_likeness_routes_high_confidence_claim_to_review(monkeypatch) -> None:
    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "find_vector_match", lambda *_args, **_kwargs: None)

    decision = policy.evaluate_text(
        "IEBC results were manipulated and falsified in 12 constituencies.",
        matcher=_matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "REVIEW"
    assert decision.labels == ["DISINFO_RISK"]
    assert "R_DISINFO_CLAIM_LIKENESS_HIGH" in decision.reason_codes
    assert decision.evidence[0].type == "model_span"
    assert decision.evidence[0].confidence is not None
    assert decision.evidence[0].confidence >= 0.7


def test_claim_likeness_does_not_override_low_non_claim_text(monkeypatch) -> None:
    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "find_vector_match", lambda *_args, **_kwargs: None)

    decision = policy.evaluate_text(
        "We should discuss policy peacefully.",
        matcher=_matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "ALLOW"
    assert decision.reason_codes == ["R_ALLOW_NO_POLICY_MATCH"]


def test_claim_likeness_thresholds_respected_from_policy_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cfg = {
        "version": "policy-claim-threshold-test",
        "model_version": "sentinel-multi-v2",
        "pack_versions": {"en": "pack-en-0.1"},
        "toxicity_by_action": {"BLOCK": 0.9, "REVIEW": 0.45, "ALLOW": 0.05},
        "allow_label": "BENIGN_POLITICAL_SPEECH",
        "allow_reason_code": "R_ALLOW_NO_POLICY_MATCH",
        "allow_confidence": 0.65,
        "claim_likeness": {
            "medium_threshold": 0.95,
            "high_threshold": 0.99,
            "require_election_anchor": True,
        },
        "phase_overrides": {},
        "language_hints": {"sw": ["na"], "sh": ["msee"]},
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("SENTINEL_POLICY_CONFIG_PATH", str(path))
    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "find_vector_match", lambda *_args, **_kwargs: None)

    decision = policy.evaluate_text(
        "Election tallies were manipulated and falsified.",
        matcher=_matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "ALLOW"
    assert decision.reason_codes == ["R_ALLOW_NO_POLICY_MATCH"]
