from __future__ import annotations

from datetime import UTC, datetime

import sentinel_api.async_worker as worker


def _item(*, content_hash: str | None, payload: dict | None = None) -> worker.QueueWorkItem:
    return worker.QueueWorkItem(
        queue_id=1,
        event_id=1,
        state="queued",
        priority="standard",
        attempt_count=0,
        sla_due_at=datetime.now(tz=UTC),
        request_id="req-1",
        source="integration",
        source_event_id="evt-1",
        lang="en",
        content_hash=content_hash,
        payload=payload or {},
        observed_at=datetime.now(tz=UTC),
        ingested_at=datetime.now(tz=UTC),
    )


def test_build_cluster_key_prefers_content_hash() -> None:
    key = worker._build_cluster_key(_item(content_hash="abc123"))
    assert key == "content:abc123"


def test_build_cluster_key_is_deterministic_without_content_hash() -> None:
    item = _item(content_hash=None, payload={"text": "sample", "n": 3})
    key1 = worker._build_cluster_key(item)
    key2 = worker._build_cluster_key(item)
    assert key1 == key2
    assert key1.startswith("event:")


def test_process_batch_stops_after_idle(monkeypatch) -> None:
    reports = [
        worker.WorkerRunReport(status="processed", queue_id=7),
        worker.WorkerRunReport(status="idle"),
        worker.WorkerRunReport(status="processed", queue_id=8),
    ]

    def _fake_process_one(*_args, **_kwargs):
        return reports.pop(0)

    monkeypatch.setattr(worker, "process_one", _fake_process_one)
    result = worker.process_batch("postgresql://example", max_items=5)
    assert [item.status for item in result] == ["processed", "idle"]


def test_retry_delay_seconds_exponential_with_cap() -> None:
    assert (
        worker._retry_delay_seconds(
            base_retry_seconds=30,
            attempt_count=1,
            max_retry_seconds=3600,
        )
        == 30
    )
    assert (
        worker._retry_delay_seconds(
            base_retry_seconds=30,
            attempt_count=2,
            max_retry_seconds=3600,
        )
        == 60
    )
    assert (
        worker._retry_delay_seconds(
            base_retry_seconds=120,
            attempt_count=8,
            max_retry_seconds=3600,
        )
        == 3600
    )


def test_can_retry_honors_attempt_limit() -> None:
    assert worker._can_retry(attempt_count=1, max_retry_attempts=5) is True
    assert worker._can_retry(attempt_count=4, max_retry_attempts=5) is True
    assert worker._can_retry(attempt_count=5, max_retry_attempts=5) is False
