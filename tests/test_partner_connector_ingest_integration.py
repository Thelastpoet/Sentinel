from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from sentinel_api.partner_connectors import (
    JsonFileFactCheckConnector,
    PartnerConnectorIngestionService,
    ResilientPartnerConnector,
)


def _integration_db_url() -> str | None:
    return os.getenv("SENTINEL_INTEGRATION_DB_URL")


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_partner_connector_ingest_writes_event_and_queue(tmp_path: Path) -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    psycopg = importlib.import_module("psycopg")

    source = "itest-partner-factcheck"
    source_event_id = f"evt-{uuid4().hex[:12]}"
    input_path = tmp_path / "partner_signals.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "source_event_id": source_event_id,
                "text": "Election violence rumor from partner feed",
                "observed_at": "2026-02-12T12:00:00+00:00",
                "request_id": "itest-partner-request",
                "lang": "en",
                "reliability_score": 5,
                "imminent_violence": True,
                "payload": {"headline": "Partner signal"},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    connector = JsonFileFactCheckConnector(name=source, input_path=input_path)
    resilient = ResilientPartnerConnector(
        connector, max_attempts=2, sleep_fn=lambda _seconds: None
    )
    service = PartnerConnectorIngestionService(
        database_url=db_url,
        connector_name=source,
        connector=resilient,
        actor="integration-suite",
    )

    first_report = service.ingest_once(limit=10)
    assert first_report.status == "ok"
    assert first_report.fetched_count == 1
    assert first_report.queued_count == 1
    assert first_report.deduplicated_count == 0
    assert first_report.invalid_count == 0

    second_report = service.ingest_once(limit=10)
    assert second_report.status == "ok"
    assert second_report.fetched_count == 1
    assert second_report.queued_count == 0
    assert second_report.deduplicated_count == 1

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, request_id
                FROM monitoring_events
                WHERE source = %s
                  AND source_event_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (source, source_event_id),
            )
            event_row = cur.fetchone()
            assert event_row is not None
            event_id = int(event_row[0])
            assert str(event_row[1]) == "itest-partner-request"

            cur.execute(
                """
                SELECT priority, state, last_actor
                FROM monitoring_queue
                WHERE event_id = %s
                """,
                (event_id,),
            )
            queue_row = cur.fetchone()
            assert queue_row is not None
            assert str(queue_row[0]) == "critical"
            assert str(queue_row[1]) == "queued"
            assert str(queue_row[2]) == "integration-suite"
