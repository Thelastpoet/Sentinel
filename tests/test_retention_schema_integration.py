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
def test_retention_primitives_schema_exists() -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    psycopg = importlib.import_module("psycopg")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT typname
                FROM pg_type
                WHERE typname = 'retention_class_t'
                """
            )
            domain = cur.fetchone()
            assert domain is not None
            assert domain[0] == "retention_class_t"

            for table in ("legal_holds", "retention_action_audit"):
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                row = cur.fetchone()
                assert row is not None
                relation_name = str(row[0])
                assert relation_name in (table, f"public.{table}")

            required_columns = {
                "lexicon_entries": {"retention_class", "legal_hold"},
                "lexicon_releases": {"retention_class", "legal_hold"},
                "release_proposals": {"retention_class", "legal_hold"},
                "proposal_reviews": {"retention_class", "legal_hold"},
                "monitoring_queue": {"retention_class", "legal_hold"},
            }
            for table_name, expected_columns in required_columns.items():
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                    """,
                    (table_name,),
                )
                found_columns = {str(row[0]) for row in cur.fetchall()}
                assert expected_columns.issubset(found_columns)
