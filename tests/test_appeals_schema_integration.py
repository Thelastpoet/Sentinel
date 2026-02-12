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
def test_appeals_tables_exist() -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    psycopg = importlib.import_module("psycopg")
    expected_tables = ["appeals", "appeal_audit"]

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for table in expected_tables:
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                row = cur.fetchone()
                assert row is not None
                relation_name = str(row[0])
                assert relation_name in (table, f"public.{table}")
