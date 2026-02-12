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
def test_async_monitoring_tables_exist() -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    psycopg = importlib.import_module("psycopg")
    expected_tables = [
        "monitoring_events",
        "monitoring_queue",
        "monitoring_queue_audit",
        "monitoring_clusters",
        "release_proposals",
        "release_proposal_audit",
        "proposal_reviews",
    ]

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for table in expected_tables:
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                found = cur.fetchone()
                assert found is not None
                relation_name = str(found[0])
                assert relation_name in (table, f"public.{table}")

            cur.execute("SELECT to_regclass(%s)", ("public.ux_monitoring_queue_event",))
            queue_event_index = cur.fetchone()
            assert queue_event_index is not None
            index_name = str(queue_event_index[0])
            assert index_name in (
                "ux_monitoring_queue_event",
                "public.ux_monitoring_queue_event",
            )
