from __future__ import annotations

import importlib
import json
import os
from uuid import uuid4

import pytest

from sentinel_api.async_priority import async_queue_metrics
from sentinel_api.async_worker import process_one


def _integration_db_url() -> str | None:
    return os.getenv("SENTINEL_INTEGRATION_DB_URL")


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_worker_consumes_queue_and_creates_proposal_with_audits() -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    async_queue_metrics.reset()
    psycopg = importlib.import_module("psycopg")

    source_event_id = f"itest-worker-{uuid4().hex[:12]}"
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO monitoring_events
                  (request_id, source, source_event_id, lang, content_hash, payload)
                VALUES
                  (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    "itest-request-1",
                    "integration-suite",
                    source_event_id,
                    "en",
                    uuid4().hex,
                    json.dumps({"text": "emerging election narrative sample"}),
                ),
            )
            event_id_row = cur.fetchone()
            assert event_id_row is not None
            event_id = int(event_id_row[0])

            cur.execute(
                """
                INSERT INTO monitoring_queue
                  (event_id, priority, state, sla_due_at, policy_impact_summary, last_actor)
                VALUES
                  (%s, 'standard', 'queued', NOW() + INTERVAL '30 minutes', %s, %s)
                RETURNING id
                """,
                (event_id, "integration-test", "integration-suite"),
            )
            queue_row = cur.fetchone()
            assert queue_row is not None
            queue_id = int(queue_row[0])
        conn.commit()

    report = process_one(db_url, worker_id="integration-worker")
    assert report.status == "processed"
    assert report.queue_id == queue_id
    assert report.cluster_id is not None
    assert report.proposal_id is not None

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT state, assigned_worker, attempt_count
                FROM monitoring_queue
                WHERE id = %s
                """,
                (queue_id,),
            )
            queue_state_row = cur.fetchone()
            assert queue_state_row is not None
            assert str(queue_state_row[0]) == "proposed"
            assert str(queue_state_row[1]) == "integration-worker"
            assert int(queue_state_row[2]) == 1

            cur.execute(
                """
                SELECT from_state, to_state, actor
                FROM monitoring_queue_audit
                WHERE queue_id = %s
                ORDER BY id ASC
                """,
                (queue_id,),
            )
            queue_audits = cur.fetchall()
            assert [str(row[1]) for row in queue_audits] == [
                "processing",
                "clustered",
                "proposed",
            ]
            assert all(str(row[2]) == "integration-worker" for row in queue_audits)

            cur.execute(
                """
                SELECT status, proposed_by, queue_id, cluster_id
                FROM release_proposals
                WHERE id = %s
                """,
                (report.proposal_id,),
            )
            proposal_row = cur.fetchone()
            assert proposal_row is not None
            assert str(proposal_row[0]) == "draft"
            assert str(proposal_row[1]) == "integration-worker"
            assert int(proposal_row[2]) == queue_id
            assert int(proposal_row[3]) == int(report.cluster_id)

            cur.execute(
                """
                SELECT to_status, actor
                FROM release_proposal_audit
                WHERE proposal_id = %s
                ORDER BY id ASC
                """,
                (report.proposal_id,),
            )
            proposal_audits = cur.fetchall()
            assert [str(row[0]) for row in proposal_audits] == ["draft"]
            assert str(proposal_audits[0][1]) == "integration-worker"

    metrics_snapshot = async_queue_metrics.snapshot()
    assert metrics_snapshot["queue_depth_by_priority"].get("standard", 0) == 0
