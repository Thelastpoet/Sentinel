from __future__ import annotations

import sentinel_api.policy as policy
from sentinel_api.lexicon_repository import LexiconEntry
from sentinel_api.policy_config import get_policy_config, reset_policy_config_cache


def setup_function() -> None:
    reset_policy_config_cache()


def teardown_function() -> None:
    reset_policy_config_cache()


def _block_entry() -> LexiconEntry:
    return LexiconEntry(
        term="kill",
        action="BLOCK",
        label="INCITEMENT_VIOLENCE",
        reason_code="R_INCITE_CALL_TO_HARM",
        severity=3,
        lang="en",
    )


def test_evaluate_text_short_circuits_on_hot_trigger_block(monkeypatch) -> None:
    entry = _block_entry()

    class _Matcher:
        version = "hatelex-v2.1"
        entries = [entry]

        def match(self, _text: str):
            raise AssertionError("lexicon scan should not run when hot trigger blocks")

    monkeypatch.setattr(
        policy,
        "find_hot_trigger_matches",
        lambda *_args, **_kwargs: [entry],
    )

    decision = policy.evaluate_text(
        "They should kill them now.",
        matcher=_Matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "BLOCK"
    assert "R_INCITE_CALL_TO_HARM" in decision.reason_codes
    assert any(item.type == "lexicon" for item in decision.evidence)


def test_evaluate_text_falls_back_to_lexicon_scan_when_hot_trigger_misses(
    monkeypatch,
) -> None:
    entry = _block_entry()

    class _Matcher:
        version = "hatelex-v2.1"
        entries = [entry]

        def match(self, _text: str):
            return [entry]

    monkeypatch.setattr(
        policy,
        "find_hot_trigger_matches",
        lambda *_args, **_kwargs: [],
    )

    decision = policy.evaluate_text(
        "They should kill them now.",
        matcher=_Matcher(),
        config=get_policy_config(),
    )
    assert decision.action == "BLOCK"
    assert "INCITEMENT_VIOLENCE" in decision.labels
