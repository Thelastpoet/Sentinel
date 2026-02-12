from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentinel_api.partner_connectors import (
    JsonFileFactCheckConnector,
    PartnerSignal,
    ResilientPartnerConnector,
    _retry_delay_seconds,
)


def test_retry_delay_seconds_exponential_with_cap() -> None:
    assert _retry_delay_seconds(attempt=1, base=2, cap=60) == 2
    assert _retry_delay_seconds(attempt=2, base=2, cap=60) == 4
    assert _retry_delay_seconds(attempt=8, base=2, cap=60) == 60


def test_json_file_connector_filters_since_and_limits(tmp_path: Path) -> None:
    input_path = tmp_path / "signals.jsonl"
    records = [
        {
            "source_event_id": "evt-1",
            "text": "first narrative",
            "observed_at": "2026-02-12T10:00:00+00:00",
            "lang": "en",
            "reliability_score": 4,
        },
        {
            "source_event_id": "evt-2",
            "text": "second narrative",
            "observed_at": "2026-02-12T11:00:00+00:00",
            "lang": "sw",
            "reliability_score": 5,
        },
    ]
    input_path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in records),
        encoding="utf-8",
    )
    connector = JsonFileFactCheckConnector(name="partner-feed", input_path=input_path)
    since = datetime(2026, 2, 12, 10, 30, tzinfo=UTC)
    signals = connector.fetch_signals(since=since, limit=10)
    assert len(signals) == 1
    assert signals[0].source_event_id == "evt-2"
    assert signals[0].payload["text"] == "second narrative"


def test_resilient_connector_retries_then_succeeds() -> None:
    class _FlakyConnector:
        name = "flaky"

        def __init__(self) -> None:
            self.calls = 0

        def fetch_signals(self, *, since=None, limit=100):  # type: ignore[no-untyped-def]
            del since, limit
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError("temporary upstream failure")
            return [
                PartnerSignal(
                    source_event_id="evt-1",
                    text="signal",
                    observed_at=datetime.now(tz=UTC),
                    payload={"text": "signal"},
                )
            ]

    sleep_calls: list[float] = []

    connector = _FlakyConnector()
    resilient = ResilientPartnerConnector(
        connector,  # type: ignore[arg-type]
        max_attempts=3,
        base_backoff_seconds=3,
        max_backoff_seconds=60,
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
    )
    outcome = resilient.fetch_signals(limit=5)
    assert outcome.status == "ok"
    assert outcome.attempts == 3
    assert len(outcome.signals) == 1
    assert sleep_calls == [3, 6]


def test_resilient_connector_opens_circuit_after_failures() -> None:
    class _AlwaysFailConnector:
        name = "always-fail"

        def __init__(self) -> None:
            self.calls = 0

        def fetch_signals(self, *, since=None, limit=100):  # type: ignore[no-untyped-def]
            del since, limit
            self.calls += 1
            raise RuntimeError("connector down")

    now = datetime(2026, 2, 12, 10, 0, tzinfo=UTC)

    def _clock() -> datetime:
        return now

    connector = _AlwaysFailConnector()
    resilient = ResilientPartnerConnector(
        connector,  # type: ignore[arg-type]
        max_attempts=1,
        circuit_failure_threshold=2,
        circuit_reset_seconds=120,
        sleep_fn=lambda _seconds: None,
        clock_fn=_clock,
    )

    first = resilient.fetch_signals(limit=1)
    second = resilient.fetch_signals(limit=1)
    third = resilient.fetch_signals(limit=1)

    assert first.status == "error"
    assert second.status == "error"
    assert third.status == "circuit_open"
    assert connector.calls == 2


def test_resilient_connector_recovers_after_circuit_timeout() -> None:
    class _RecoveringConnector:
        name = "recovering"

        def __init__(self) -> None:
            self.calls = 0

        def fetch_signals(self, *, since=None, limit=100):  # type: ignore[no-untyped-def]
            del since, limit
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("first call fails")
            return [
                PartnerSignal(
                    source_event_id="evt-ok",
                    text="ok",
                    observed_at=datetime.now(tz=UTC),
                    payload={"text": "ok"},
                )
            ]

    now = datetime(2026, 2, 12, 10, 0, tzinfo=UTC)

    def _clock() -> datetime:
        return now

    connector = _RecoveringConnector()
    resilient = ResilientPartnerConnector(
        connector,  # type: ignore[arg-type]
        max_attempts=1,
        circuit_failure_threshold=1,
        circuit_reset_seconds=60,
        sleep_fn=lambda _seconds: None,
        clock_fn=_clock,
    )

    first = resilient.fetch_signals(limit=1)
    assert first.status == "error"

    blocked = resilient.fetch_signals(limit=1)
    assert blocked.status == "circuit_open"

    now = now + timedelta(seconds=61)
    recovered = resilient.fetch_signals(limit=1)
    assert recovered.status == "ok"
    assert recovered.attempts == 1
    assert len(recovered.signals) == 1
