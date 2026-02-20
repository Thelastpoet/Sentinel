from __future__ import annotations

import logging
import math

from sentinel_api import vector_matcher


def setup_function() -> None:
    vector_matcher.reset_vector_match_cache()


def teardown_function() -> None:
    vector_matcher.reset_vector_match_cache()


def test_embed_text_returns_normalized_vector() -> None:
    vector = vector_matcher.embed_text("Election narrative manipulation")
    assert len(vector) == vector_matcher.VECTOR_DIMENSION
    assert any(value != 0 for value in vector)
    norm = sum(value * value for value in vector) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_find_vector_match_returns_none_without_database(monkeypatch) -> None:
    monkeypatch.delenv("SENTINEL_DATABASE_URL", raising=False)
    result = vector_matcher.find_vector_match(
        "election manipulation narrative",
        lexicon_version="hatelex-v2.1",
        query_embedding=vector_matcher.embed_text("election manipulation narrative"),
        embedding_model=vector_matcher.VECTOR_MODEL,
    )
    assert result is None


def test_find_vector_match_returns_none_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example")
    monkeypatch.setenv("SENTINEL_VECTOR_MATCH_ENABLED", "false")
    result = vector_matcher.find_vector_match(
        "election manipulation narrative",
        lexicon_version="hatelex-v2.1",
        query_embedding=vector_matcher.embed_text("election manipulation narrative"),
        embedding_model=vector_matcher.VECTOR_MODEL,
    )
    assert result is None


def test_find_vector_match_returns_result_when_similarity_meets_threshold(
    monkeypatch,
) -> None:
    state = {"upserts": 0}

    class _Cursor:
        def __init__(self) -> None:
            self._fetchall_result = []
            self._fetchone_result = None

        def execute(self, query: str, params=None) -> None:
            if "LEFT JOIN lexicon_entry_embeddings_v2" in query:
                self._fetchall_result = [(7, "rigged")]
                return
            if "INSERT INTO lexicon_entry_embeddings_v2" in query:
                state["upserts"] += 1
                return
            if "JOIN lexicon_entry_embeddings_v2 AS emb" in query:
                self._fetchone_result = (
                    7,
                    "rigged",
                    "REVIEW",
                    "DISINFO_RISK",
                    "R_DISINFO_NARRATIVE_SIMILARITY",
                    1,
                    "en",
                    0.91,
                )

        def fetchall(self):
            return self._fetchall_result

        def fetchone(self):
            return self._fetchone_result

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _Connection:
        def cursor(self) -> _Cursor:
            return _Cursor()

        def commit(self) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _FakePsycopg:
        def connect(self, _database_url: str) -> _Connection:
            return _Connection()

    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example")
    monkeypatch.setenv("SENTINEL_VECTOR_MATCH_THRESHOLD", "0.8")
    monkeypatch.setattr(vector_matcher, "_get_psycopg_module", lambda: _FakePsycopg())

    match = vector_matcher.find_vector_match(
        "they manipulated election results",
        lexicon_version="hatelex-v2.1",
        query_embedding=vector_matcher.embed_text("they manipulated election results"),
        embedding_model=vector_matcher.VECTOR_MODEL,
    )

    assert match is not None
    assert match.entry.term == "rigged"
    assert match.match_id == "7"
    assert match.similarity == 0.91
    assert state["upserts"] == 1


def test_find_vector_match_logs_warning_on_non_finite_similarity(monkeypatch, caplog) -> None:
    class _Cursor:
        def __init__(self) -> None:
            self._fetchall_result = []
            self._fetchone_result = None

        def execute(self, query: str, params=None) -> None:
            if "LEFT JOIN lexicon_entry_embeddings_v2" in query:
                self._fetchall_result = []
                return
            if "JOIN lexicon_entry_embeddings_v2 AS emb" in query:
                self._fetchone_result = (
                    13,
                    "rigged",
                    "REVIEW",
                    "DISINFO_RISK",
                    "R_DISINFO_NARRATIVE_SIMILARITY",
                    1,
                    "en",
                    math.nan,
                )

        def fetchall(self):
            return self._fetchall_result

        def fetchone(self):
            return self._fetchone_result

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _Connection:
        def cursor(self) -> _Cursor:
            return _Cursor()

        def commit(self) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _FakePsycopg:
        def connect(self, _database_url: str) -> _Connection:
            return _Connection()

    caplog.set_level(logging.WARNING, logger="sentinel_lexicon.vector_matcher")
    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(vector_matcher, "_get_psycopg_module", lambda: _FakePsycopg())
    result = vector_matcher.find_vector_match(
        "they manipulated election results",
        lexicon_version="hatelex-v2.1",
        query_embedding=vector_matcher.embed_text("they manipulated election results"),
        embedding_model=vector_matcher.VECTOR_MODEL,
    )
    assert result is None
    assert "vector similarity was non-finite" in caplog.text
