from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sentinel_api.async_priority import (
    AsyncQueueMetrics,
    Priority,
    PrioritySignals,
    classify_priority,
    is_sla_breached,
    seconds_until_sla_due,
    sla_due_at,
)


def test_classify_priority_manual_override_wins() -> None:
    signals = PrioritySignals(imminent_violence=True, manual_priority="batch")
    assert classify_priority(signals) == "batch"


def test_classify_priority_imminent_violence_is_critical() -> None:
    signals = PrioritySignals(imminent_violence=True)
    assert classify_priority(signals) == "critical"


def test_classify_priority_campaign_spike_is_urgent() -> None:
    signals = PrioritySignals(campaign_disinfo_spike=True)
    assert classify_priority(signals) == "urgent"


def test_classify_priority_high_reliability_is_urgent() -> None:
    signals = PrioritySignals(source_reliability=5)
    assert classify_priority(signals) == "urgent"


def test_classify_priority_backfill_is_batch() -> None:
    signals = PrioritySignals(is_backfill=True)
    assert classify_priority(signals) == "batch"


def test_classify_priority_default_is_standard() -> None:
    assert classify_priority(PrioritySignals()) == "standard"


def test_classify_priority_rejects_bad_reliability() -> None:
    with pytest.raises(ValueError):
        classify_priority(PrioritySignals(source_reliability=0))


@pytest.mark.parametrize(
    ("priority", "expected_delta"),
    [
        ("critical", timedelta(minutes=5)),
        ("urgent", timedelta(minutes=30)),
        ("standard", timedelta(hours=4)),
        ("batch", timedelta(hours=24)),
    ],
)
def test_sla_due_at_uses_expected_windows(
    priority: Priority, expected_delta: timedelta
) -> None:
    queued_at = datetime(2026, 2, 12, 12, 0, tzinfo=UTC)
    due = sla_due_at(priority, queued_at)
    assert due == queued_at + expected_delta


def test_seconds_until_sla_due_and_breach() -> None:
    queued_at = datetime(2026, 2, 12, 12, 0, tzinfo=UTC)
    now_before = queued_at + timedelta(minutes=4)
    now_after = queued_at + timedelta(minutes=6)

    assert seconds_until_sla_due("critical", queued_at, now_before) == 60
    assert is_sla_breached("critical", queued_at, now_before) is False
    assert seconds_until_sla_due("critical", queued_at, now_after) == 0
    assert is_sla_breached("critical", queued_at, now_after) is True


def test_sla_functions_require_timezone_aware_timestamps() -> None:
    naive = datetime(2026, 2, 12, 12, 0)
    with pytest.raises(ValueError):
        sla_due_at("critical", naive)


def test_async_queue_metrics_counters_and_alerts() -> None:
    metrics = AsyncQueueMetrics()
    metrics.set_queue_depth("urgent", 3)
    metrics.increment_sla_breach("urgent", count=5)

    snapshot = metrics.snapshot()
    assert snapshot["queue_depth_by_priority"]["urgent"] == 3
    assert snapshot["sla_breach_count_by_priority"]["urgent"] == 5

    alerts = metrics.evaluate_sla_alerts()
    assert alerts["urgent"] is True
    assert alerts["critical"] is False
