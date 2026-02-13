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
def test_model_artifact_schema_exists() -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    psycopg = importlib.import_module("psycopg")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT typname
                FROM pg_type
                WHERE typname = 'model_artifact_status_t'
                """
            )
            domain_row = cur.fetchone()
            assert domain_row is not None
            assert domain_row[0] == "model_artifact_status_t"

            for table in ("model_artifacts", "model_artifact_audit"):
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                table_row = cur.fetchone()
                assert table_row is not None
                relation_name = str(table_row[0])
                assert relation_name in (table, f"public.{table}")

            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'model_artifacts'
                  AND indexname = 'ux_model_artifacts_single_active'
                """
            )
            index_row = cur.fetchone()
            assert index_row is not None
            assert index_row[0] == "ux_model_artifacts_single_active"
