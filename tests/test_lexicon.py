from __future__ import annotations

from sentinel_api import lexicon
from sentinel_api.lexicon import reset_lexicon_cache
from sentinel_api.lexicon_repository import LexiconEntry, LexiconSnapshot


def setup_function() -> None:
    reset_lexicon_cache()


def teardown_function() -> None:
    reset_lexicon_cache()


def test_get_lexicon_matcher_uses_file_when_db_not_set(monkeypatch) -> None:
    monkeypatch.delenv("SENTINEL_DATABASE_URL", raising=False)
    matcher = lexicon.get_lexicon_matcher()
    assert matcher.version == "hatelex-v2.1"
    assert any(entry.term == "kill" for entry in matcher.entries)


def test_get_lexicon_matcher_prefers_postgres(monkeypatch) -> None:
    class FakeRepo:
        def fetch_active(self) -> LexiconSnapshot:
            return LexiconSnapshot(
                version="hatelex-v9.9",
                entries=[
                    LexiconEntry(
                        term="foo",
                        action="REVIEW",
                        label="DOGWHISTLE_WATCH",
                        reason_code="R_DOGWHISTLE_CONTEXT_REQUIRED",
                        severity=2,
                        lang="en",
                    )
                ],
            )

    monkeypatch.setattr(lexicon, "_build_repository_from_env", lambda: FakeRepo())
    matcher = lexicon.get_lexicon_matcher()
    assert matcher.version == "hatelex-v9.9"
    assert matcher.entries[0].term == "foo"


def test_get_lexicon_matcher_falls_back_when_postgres_fails(monkeypatch) -> None:
    class _FailingRepo:
        def fetch_active(self) -> LexiconSnapshot:
            raise RuntimeError("db unavailable")

    class _StaticRepo:
        def fetch_active(self) -> LexiconSnapshot:
            return LexiconSnapshot(
                version="hatelex-v2.1",
                entries=[
                    LexiconEntry(
                        term="kill",
                        action="BLOCK",
                        label="INCITEMENT_VIOLENCE",
                        reason_code="R_INCITE_CALL_TO_HARM",
                        severity=3,
                        lang="en",
                    )
                ],
            )

    class _NoOpLogger:
        def warning(self, *_args, **_kwargs) -> None:
            return None

    from sentinel_api.lexicon_repository import FallbackLexiconRepository

    monkeypatch.setattr(
        lexicon,
        "_build_repository_from_env",
        lambda: FallbackLexiconRepository(
            primary=_FailingRepo(),
            fallback=_StaticRepo(),
            logger=_NoOpLogger(),
        ),
    )
    matcher = lexicon.get_lexicon_matcher()
    assert matcher.version == "hatelex-v2.1"
    assert any(entry.term == "kill" for entry in matcher.entries)
