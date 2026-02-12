from __future__ import annotations

from sentinel_api.lexicon import LexiconMatcher
from sentinel_api.lexicon_repository import LexiconEntry


def _entry(term: str, *, action: str = "BLOCK") -> LexiconEntry:
    return LexiconEntry(
        term=term,
        action=action,
        label="INCITEMENT_VIOLENCE" if action == "BLOCK" else "DOGWHISTLE_WATCH",
        reason_code=(
            "R_INCITE_CALL_TO_HARM"
            if action == "BLOCK"
            else "R_DOGWHISTLE_CONTEXT_REQUIRED"
        ),
        severity=3 if action == "BLOCK" else 2,
        lang="en",
    )


def test_matcher_matches_single_word_term_with_boundaries() -> None:
    matcher = LexiconMatcher(version="v", entries=[_entry("kill")])
    matches = matcher.match("They should kill them now.")
    assert len(matches) == 1
    assert matches[0].term == "kill"


def test_matcher_does_not_match_term_inside_larger_word() -> None:
    matcher = LexiconMatcher(version="v", entries=[_entry("kill")])
    matches = matcher.match("This skill matters for campaign safety.")
    assert matches == []


def test_matcher_matches_phrase_term_across_punctuation() -> None:
    matcher = LexiconMatcher(version="v", entries=[_entry("burn them")])
    matches = matcher.match("They said: burn, them now.")
    assert len(matches) == 1
    assert matches[0].term == "burn them"


def test_matcher_normalizes_case_and_unicode_apostrophe() -> None:
    matcher = LexiconMatcher(version="v", entries=[_entry("MCHOME")])
    matches = matcher.match("Mchome now!")
    assert len(matches) == 1
    assert matches[0].term == "MCHOME"
