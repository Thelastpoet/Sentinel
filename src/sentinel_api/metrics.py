from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Any, TypedDict

try:
    from prometheus_client import (
        CollectorRegistry as PromCollectorRegistry,
    )
    from prometheus_client import (
        Counter as PromCounter,
    )
    from prometheus_client import (
        Histogram as PromHistogram,
    )
    from prometheus_client import (
        generate_latest,
    )
except Exception:  # pragma: no cover - optional runtime dependency
    PromCollectorRegistry = None  # type: ignore[assignment,misc]
    PromCounter = None  # type: ignore[assignment,misc]
    PromHistogram = None  # type: ignore[assignment,misc]
    generate_latest = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry as PromCollectorRegistryType
    from prometheus_client import Counter as PromCounterType
    from prometheus_client import Histogram as PromHistogramType
else:
    PromCollectorRegistryType = Any
    PromCounterType = Any
    PromHistogramType = Any

LATENCY_BUCKET_THRESHOLDS_MS = (50, 100, 150, 300, 1000)


class MetricsSnapshot(TypedDict):
    action_counts: dict[str, int]
    http_status_counts: dict[str, int]
    latency_ms_buckets: dict[str, int]
    validation_error_count: int


def _latency_bucket(latency_ms: int) -> str:
    if latency_ms < 0:
        latency_ms = 0
    for threshold in LATENCY_BUCKET_THRESHOLDS_MS:
        if latency_ms <= threshold:
            return f"le_{threshold}ms"
    return "gt_1000ms"


@dataclass
class InMemoryMetrics:
    lock: Lock = field(default_factory=Lock)
    action_counts: Counter[str] = field(default_factory=Counter)
    http_status_counts: Counter[int] = field(default_factory=Counter)
    latency_ms_buckets: Counter[str] = field(default_factory=Counter)
    validation_error_count: int = 0
    _registry: PromCollectorRegistryType | None = field(default=None, init=False, repr=False)
    _action_total: PromCounterType | None = field(default=None, init=False, repr=False)
    _http_status_total: PromCounterType | None = field(default=None, init=False, repr=False)
    _validation_error_total: PromCounterType | None = field(default=None, init=False, repr=False)
    _moderation_latency_ms: PromHistogramType | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            PromCollectorRegistry is None
            or PromCounter is None
            or PromHistogram is None
            or generate_latest is None
        ):
            return
        self._registry = PromCollectorRegistry()
        self._action_total = PromCounter(
            "sentinel_action_total",
            "Total moderation decisions by action.",
            ["action"],
            registry=self._registry,
        )
        self._http_status_total = PromCounter(
            "sentinel_http_status_total",
            "Total HTTP responses by status code.",
            ["status_code"],
            registry=self._registry,
        )
        self._validation_error_total = PromCounter(
            "sentinel_validation_error_total",
            "Total request validation errors.",
            registry=self._registry,
        )
        histogram_buckets = tuple(float(value) for value in LATENCY_BUCKET_THRESHOLDS_MS)
        self._moderation_latency_ms = PromHistogram(
            "sentinel_moderation_latency_ms",
            "Moderation latency in milliseconds.",
            buckets=histogram_buckets + (float("inf"),),
            registry=self._registry,
        )

    def record_action(self, action: str) -> None:
        with self.lock:
            self.action_counts[action] += 1
            if self._action_total is not None:
                self._action_total.labels(action=action).inc()

    def record_http_status(self, status_code: int) -> None:
        with self.lock:
            self.http_status_counts[status_code] += 1
            if self._http_status_total is not None:
                self._http_status_total.labels(status_code=str(status_code)).inc()

    def record_moderation_latency(self, latency_ms: int) -> None:
        bucket = _latency_bucket(latency_ms)
        with self.lock:
            self.latency_ms_buckets[bucket] += 1
            if self._moderation_latency_ms is not None:
                self._moderation_latency_ms.observe(float(max(0, latency_ms)))

    def record_validation_error(self) -> None:
        with self.lock:
            self.validation_error_count += 1
            if self._validation_error_total is not None:
                self._validation_error_total.inc()

    def snapshot(self) -> MetricsSnapshot:
        with self.lock:
            return {
                "action_counts": dict(self.action_counts),
                "http_status_counts": {
                    str(status): count for status, count in self.http_status_counts.items()
                },
                "latency_ms_buckets": dict(self.latency_ms_buckets),
                "validation_error_count": self.validation_error_count,
            }

    def reset(self) -> None:
        with self.lock:
            self.action_counts.clear()
            self.http_status_counts.clear()
            self.latency_ms_buckets.clear()
            self.validation_error_count = 0

    def prometheus_text(self) -> str:
        if self._registry is None or generate_latest is None:
            return ""
        return generate_latest(self._registry).decode("utf-8")


metrics = InMemoryMetrics()
