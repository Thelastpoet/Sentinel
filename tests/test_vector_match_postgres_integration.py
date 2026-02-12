from __future__ import annotations

import importlib
import os

import pytest

from sentinel_api.vector_matcher import find_vector_match, reset_vector_match_cache


def _integration_db_url() -> str | None:
    return os.getenv("SENTINEL_INTEGRATION_DB_URL")


def setup_function() -> None:
    reset_vector_match_cache()


def teardown_function() -> None:
    reset_vector_match_cache()


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_pgvector_match_populates_embedding_table_and_returns_candidate(
    monkeypatch,
) -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    monkeypatch.setenv("SENTINEL_DATABASE_URL", db_url)
    monkeypatch.setenv("SENTINEL_VECTOR_MATCH_THRESHOLD", "0.95")

    match = find_vector_match(
        "rigged",
        lexicon_version="hatelex-v2.1",
    )
    assert match is not None
    assert match.match_id
    assert match.entry.term == "rigged"
    assert match.entry.action == "REVIEW"
    assert 0.95 <= match.similarity <= 1

    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(1) FROM lexicon_entry_embeddings")
            row = cur.fetchone()
            assert row is not None
            assert int(row[0]) > 0
