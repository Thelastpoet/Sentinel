from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from threading import Lock


LATENCY_BUCKET_THRESHOLDS_MS = (50, 100, 150, 300, 1000)


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

    def record_action(self, action: str) -> None:
        with self.lock:
            self.action_counts[action] += 1

    def record_http_status(self, status_code: int) -> None:
        with self.lock:
            self.http_status_counts[status_code] += 1

    def record_moderation_latency(self, latency_ms: int) -> None:
        bucket = _latency_bucket(latency_ms)
        with self.lock:
            self.latency_ms_buckets[bucket] += 1

    def record_validation_error(self) -> None:
        with self.lock:
            self.validation_error_count += 1

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {
                "action_counts": dict(self.action_counts),
                "http_status_counts": {
                    str(status): count
                    for status, count in self.http_status_counts.items()
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


metrics = InMemoryMetrics()
