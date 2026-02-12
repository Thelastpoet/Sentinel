from __future__ import annotations

import importlib
import os

import pytest


def _integration_db_url() -> str | None:
    return os.getenv("SENTINEL_INTEGRATION_DB_URL")


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_vector_embedding_table_exists() -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", ("public.lexicon_entry_embeddings",))
            row = cur.fetchone()
            assert row is not None
            assert row[0] in {"lexicon_entry_embeddings", "public.lexicon_entry_embeddings"}
