from __future__ import annotations

import pytest

from sentinel_api.benchmark import percentile, summarize_latency


def test_percentile_p95_uses_ceiling_rank() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(values, 0.95) == 5.0


def test_summarize_latency_returns_expected_fields() -> None:
    summary = summarize_latency([10.0, 20.0, 30.0, 40.0, 50.0])
    assert summary["count"] == 5.0
    assert summary["min_ms"] == 10.0
    assert summary["mean_ms"] == 30.0
    assert summary["p95_ms"] == 50.0
    assert summary["max_ms"] == 50.0


def test_summarize_latency_requires_data() -> None:
    with pytest.raises(ValueError):
        summarize_latency([])
