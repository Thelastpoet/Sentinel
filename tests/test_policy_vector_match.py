from __future__ import annotations

import sentinel_api.policy as policy
from sentinel_api.lexicon_repository import LexiconEntry
from sentinel_api.policy_config import get_policy_config, reset_policy_config_cache
from sentinel_api.vector_matcher import VectorMatch, reset_vector_match_cache


def setup_function() -> None:
    reset_policy_config_cache()
    reset_vector_match_cache()


def teardown_function() -> None:
    reset_policy_config_cache()
    reset_vector_match_cache()


def test_evaluate_text_uses_vector_match_when_lexicon_has_no_hits(monkeypatch) -> None:
    vector_entry = LexiconEntry(
        term="rigged",
        action="REVIEW",
        label="DISINFO_RISK",
        reason_code="R_DISINFO_NARRATIVE_SIMILARITY",
        severity=1,
        lang="en",
    )

    class _Matcher:
        version = "hatelex-v2.1"
        entries: list[LexiconEntry] = []

        def match(self, _text: str) -> list[LexiconEntry]:
            return []

    monkeypatch.setattr(
        policy,
        "find_hot_trigger_matches",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        policy,
        "find_vector_match",
        lambda *_args, **_kwargs: VectorMatch(
            entry=vector_entry,
            similarity=0.88,
            match_id="101",
        ),
    )

    decision = policy.evaluate_text(
        "they manipulated election tallies",
        matcher=_Matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "REVIEW"
    assert decision.labels == ["DISINFO_RISK"]
    assert decision.reason_codes == ["R_DISINFO_NARRATIVE_SIMILARITY"]
    assert decision.evidence[0].type == "vector_match"
    assert decision.evidence[0].match == "rigged"
    assert decision.evidence[0].match_id == "101"
    assert decision.evidence[0].similarity == 0.88


def test_evaluate_text_prefers_lexicon_review_before_vector(monkeypatch) -> None:
    lexicon_entry = LexiconEntry(
        term="deal with them",
        action="REVIEW",
        label="DOGWHISTLE_WATCH",
        reason_code="R_DOGWHISTLE_CONTEXT_REQUIRED",
        severity=2,
        lang="en",
    )

    class _Matcher:
        version = "hatelex-v2.1"
        entries = [lexicon_entry]

        def match(self, _text: str) -> list[LexiconEntry]:
            return [lexicon_entry]

    monkeypatch.setattr(
        policy,
        "find_hot_trigger_matches",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        policy,
        "find_vector_match",
        lambda *_args, **_kwargs: None,
    )

    decision = policy.evaluate_text(
        "we should deal with them politically",
        matcher=_Matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "REVIEW"
    assert decision.reason_codes == ["R_DOGWHISTLE_CONTEXT_REQUIRED"]
    assert decision.evidence[0].type == "lexicon"


def test_evaluate_text_vector_match_never_directly_blocks(monkeypatch) -> None:
    vector_entry = LexiconEntry(
        term="kill",
        action="BLOCK",
        label="INCITEMENT_VIOLENCE",
        reason_code="R_INCITE_CALL_TO_HARM",
        severity=3,
        lang="en",
    )

    class _Matcher:
        version = "hatelex-v2.1"
        entries: list[LexiconEntry] = []

        def match(self, _text: str) -> list[LexiconEntry]:
            return []

    monkeypatch.setattr(
        policy,
        "find_hot_trigger_matches",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        policy,
        "find_vector_match",
        lambda *_args, **_kwargs: VectorMatch(
            entry=vector_entry,
            similarity=0.99,
            match_id="7",
        ),
    )

    decision = policy.evaluate_text(
        "election claim text",
        matcher=_Matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "REVIEW"
    assert decision.reason_codes == ["R_INCITE_CALL_TO_HARM"]
    assert decision.evidence[0].type == "vector_match"
