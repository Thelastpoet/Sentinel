from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Literal, cast

Priority = Literal["critical", "urgent", "standard", "batch"]

SLA_WINDOWS: dict[Priority, timedelta] = {
    "critical": timedelta(minutes=5),
    "urgent": timedelta(minutes=30),
    "standard": timedelta(hours=4),
    "batch": timedelta(hours=24),
}


@dataclass(frozen=True)
class PrioritySignals:
    imminent_violence: bool = False
    campaign_disinfo_spike: bool = False
    source_reliability: int | None = None
    is_backfill: bool = False
    manual_priority: Priority | None = None


def _validate_priority(priority: str) -> Priority:
    if priority not in SLA_WINDOWS:
        raise ValueError(f"unknown priority: {priority}")
    return cast(Priority, priority)


def _validate_reliability(value: int | None) -> None:
    if value is None:
        return
    if value < 1 or value > 5:
        raise ValueError("source_reliability must be in range 1..5")


def classify_priority(signals: PrioritySignals) -> Priority:
    _validate_reliability(signals.source_reliability)

    if signals.manual_priority is not None:
        return _validate_priority(signals.manual_priority)
    if signals.imminent_violence:
        return "critical"
    if signals.campaign_disinfo_spike:
        return "urgent"
    if signals.source_reliability is not None and signals.source_reliability >= 4:
        return "urgent"
    if signals.is_backfill:
        return "batch"
    return "standard"


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


def sla_due_at(priority: Priority, queued_at: datetime) -> datetime:
    normalized = _normalize_timestamp(queued_at)
    return normalized + SLA_WINDOWS[_validate_priority(priority)]


def seconds_until_sla_due(priority: Priority, queued_at: datetime, now: datetime) -> int:
    due = sla_due_at(priority, queued_at)
    now_utc = _normalize_timestamp(now)
    remaining = int((due - now_utc).total_seconds())
    return max(0, remaining)


def is_sla_breached(priority: Priority, queued_at: datetime, now: datetime) -> bool:
    due = sla_due_at(priority, queued_at)
    return _normalize_timestamp(now) > due


@dataclass
class AsyncQueueMetrics:
    lock: Lock = field(default_factory=Lock)
    queue_depth_by_priority: Counter[str] = field(default_factory=Counter)
    sla_breach_count_by_priority: Counter[str] = field(default_factory=Counter)

    def set_queue_depth(self, priority: Priority, depth: int) -> None:
        _validate_priority(priority)
        if depth < 0:
            raise ValueError("depth must be >= 0")
        with self.lock:
            self.queue_depth_by_priority[priority] = depth

    def increment_sla_breach(self, priority: Priority, count: int = 1) -> None:
        _validate_priority(priority)
        if count <= 0:
            raise ValueError("count must be > 0")
        with self.lock:
            self.sla_breach_count_by_priority[priority] += count

    def evaluate_sla_alerts(
        self, thresholds: dict[Priority, int] | None = None
    ) -> dict[str, bool]:
        threshold_map = thresholds or {
            "critical": 1,
            "urgent": 5,
            "standard": 10,
            "batch": 20,
        }
        with self.lock:
            return {
                priority: self.sla_breach_count_by_priority[priority]
                >= threshold_map[priority]
                for priority in SLA_WINDOWS
            }

    def snapshot(self) -> dict[str, dict[str, int]]:
        with self.lock:
            return {
                "queue_depth_by_priority": dict(self.queue_depth_by_priority),
                "sla_breach_count_by_priority": dict(self.sla_breach_count_by_priority),
            }

    def reset(self) -> None:
        with self.lock:
            self.queue_depth_by_priority.clear()
            self.sla_breach_count_by_priority.clear()


async_queue_metrics = AsyncQueueMetrics()
