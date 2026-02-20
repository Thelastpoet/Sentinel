from __future__ import annotations

from pathlib import Path

import sentinel_api.policy as policy
from sentinel_api.policy_config import get_policy_config, reset_policy_config_cache
from sentinel_langpack import get_wave1_pack_matchers


class _Matcher:
    version = "hatelex-v2.1"
    entries = []

    def match(self, _text: str):  # type: ignore[no-untyped-def]
        return []


def setup_function() -> None:
    reset_policy_config_cache()


def teardown_function() -> None:
    reset_policy_config_cache()


def test_luo_term_routes_to_review(monkeypatch) -> None:
    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "find_vector_match", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(policy, "score_claim_with_fallback", lambda *_args, **_kwargs: None)

    decision = policy.evaluate_text(
        "this contains chok-ruok",
        matcher=_Matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "REVIEW"
    assert decision.evidence
    assert decision.evidence[0].type == "lexicon"
    assert decision.evidence[0].lang == "luo"
    assert decision.reason_codes == ["R_LUO_INCITE_LEXICON"]


def test_kalenjin_term_routes_to_review(monkeypatch) -> None:
    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "find_vector_match", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(policy, "score_claim_with_fallback", lambda *_args, **_kwargs: None)

    decision = policy.evaluate_text(
        "met-incite should match after normalization",
        matcher=_Matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "REVIEW"
    assert decision.evidence
    assert decision.evidence[0].type == "lexicon"
    assert decision.evidence[0].lang == "kalenjin"
    assert decision.reason_codes == ["R_KLN_INCITE_LEXICON"]


def test_pack_match_never_produces_block(monkeypatch) -> None:
    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "find_vector_match", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(policy, "score_claim_with_fallback", lambda *_args, **_kwargs: None)

    decision = policy.evaluate_text(
        "jodak-slur appears here",
        matcher=_Matcher(),
        config=get_policy_config(),
    )
    assert decision.action != "BLOCK"


def test_missing_registry_returns_empty_matchers(monkeypatch, tmp_path: Path) -> None:
    import sentinel_langpack.hot_path as hot_path

    hot_path.get_wave1_pack_matchers.cache_clear()
    monkeypatch.setattr(hot_path, "DEFAULT_REGISTRY_PATH", tmp_path / "missing.json")
    hot_path.get_wave1_pack_matchers.cache_clear()
    assert get_wave1_pack_matchers() == []
