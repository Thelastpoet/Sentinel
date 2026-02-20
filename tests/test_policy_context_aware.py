from __future__ import annotations

import sentinel_api.policy as policy
from sentinel_api.lexicon_repository import LexiconEntry
from sentinel_api.policy_config import reset_policy_config_cache, resolve_policy_runtime
from sentinel_api.vector_matcher import VectorMatch
from sentinel_core.models import ModerationContext


class _Matcher:
    version = "hatelex-v2.1"
    entries = []

    def match(self, _text: str):  # type: ignore[no-untyped-def]
        return []


def setup_function() -> None:
    reset_policy_config_cache()


def teardown_function() -> None:
    reset_policy_config_cache()


def test_forward_channel_lowers_threshold(monkeypatch) -> None:
    vector_entry = LexiconEntry(
        term="rigged",
        action="REVIEW",
        label="DISINFO_RISK",
        reason_code="R_DISINFO_NARRATIVE_SIMILARITY",
        severity=1,
        lang="en",
    )

    def _vector_stub(
        _text: str,
        *,
        lexicon_version: str,
        query_embedding: list[float],
        embedding_model: str,
        min_similarity: float | None = None,
    ):
        assert lexicon_version == "hatelex-v2.1"
        assert embedding_model
        assert query_embedding
        if min_similarity is None:
            return None
        if min_similarity <= 0.80:
            return VectorMatch(entry=vector_entry, similarity=0.80, match_id="55")
        return None

    runtime = resolve_policy_runtime().model_copy(update={"vector_match_threshold": 0.82})

    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "get_wave1_pack_matchers", lambda: [])
    monkeypatch.setattr(policy, "find_vector_match", _vector_stub)
    monkeypatch.setattr(policy, "score_claim_with_fallback", lambda *_args, **_kwargs: None)

    forward_context = ModerationContext(channel="forward")
    decision = policy.evaluate_text(
        "they manipulated election tallies",
        matcher=_Matcher(),
        runtime=runtime,
        context=forward_context,
    )
    assert decision.action == "REVIEW"
    assert decision.evidence[0].type == "vector_match"

    neutral_decision = policy.evaluate_text(
        "they manipulated election tallies",
        matcher=_Matcher(),
        runtime=runtime,
        context=None,
    )
    assert neutral_decision.action == "ALLOW"


def test_broadcast_channel_raises_threshold(monkeypatch) -> None:
    vector_entry = LexiconEntry(
        term="rigged",
        action="REVIEW",
        label="DISINFO_RISK",
        reason_code="R_DISINFO_NARRATIVE_SIMILARITY",
        severity=1,
        lang="en",
    )

    def _vector_stub(
        _text: str,
        *,
        lexicon_version: str,
        query_embedding: list[float],
        embedding_model: str,
        min_similarity: float | None = None,
    ):
        del lexicon_version
        assert embedding_model
        assert query_embedding
        if min_similarity is None:
            return None
        if min_similarity <= 0.80:
            return VectorMatch(entry=vector_entry, similarity=0.80, match_id="55")
        return None

    runtime = resolve_policy_runtime().model_copy(update={"vector_match_threshold": 0.82})

    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "get_wave1_pack_matchers", lambda: [])
    monkeypatch.setattr(policy, "find_vector_match", _vector_stub)
    monkeypatch.setattr(policy, "score_claim_with_fallback", lambda *_args, **_kwargs: None)

    broadcast_context = ModerationContext(channel="broadcast")
    decision = policy.evaluate_text(
        "they manipulated election tallies",
        matcher=_Matcher(),
        runtime=runtime,
        context=broadcast_context,
    )
    assert decision.action == "ALLOW"


def test_partner_factcheck_amplifies_claim_score(monkeypatch) -> None:
    runtime = resolve_policy_runtime()

    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "get_wave1_pack_matchers", lambda: [])
    monkeypatch.setattr(policy, "find_vector_match", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(policy, "score_claim_with_fallback", lambda *_args, **_kwargs: (0.44, "x"))

    baseline = policy.evaluate_text(
        "election results were manipulated",
        matcher=_Matcher(),
        runtime=runtime,
        context=ModerationContext(source="other"),
    )
    assert baseline.action == "ALLOW"

    amplified = policy.evaluate_text(
        "election results were manipulated",
        matcher=_Matcher(),
        runtime=runtime,
        context=ModerationContext(source="partner_factcheck"),
    )
    assert amplified.action == "REVIEW"
    assert amplified.reason_codes == ["R_DISINFO_CLAIM_LIKENESS_MEDIUM"]


def test_null_context_no_change(monkeypatch) -> None:
    runtime = resolve_policy_runtime().model_copy(update={"vector_match_threshold": 0.82})

    called: list[float] = []

    def _vector_stub(
        _text: str,
        *,
        lexicon_version: str,
        query_embedding: list[float],
        embedding_model: str,
        min_similarity: float | None = None,
    ):
        del lexicon_version, query_embedding, embedding_model
        called.append(min_similarity if min_similarity is not None else -1.0)
        return None

    monkeypatch.setattr(policy, "find_hot_trigger_matches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(policy, "get_wave1_pack_matchers", lambda: [])
    monkeypatch.setattr(policy, "find_vector_match", _vector_stub)
    monkeypatch.setattr(policy, "score_claim_with_fallback", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example")

    policy.evaluate_text(
        "peaceful discussion",
        matcher=_Matcher(),
        runtime=runtime,
        context=None,
    )
    policy.evaluate_text(
        "peaceful discussion",
        matcher=_Matcher(),
        runtime=runtime,
        context=ModerationContext(channel="unknown"),
    )
    assert called == [0.82, 0.82]
