from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass
from threading import Lock

AUDIT_RING_BUFFER_SIZE = 1000


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    action: str
    labels: list[str]
    reason_codes: list[str]
    latency_ms: int
    deployment_stage: str
    lexicon_version: str
    policy_version: str


_lock = Lock()
_sequence: int = 0
_ring: deque[tuple[int, AuditEvent]] = deque(maxlen=AUDIT_RING_BUFFER_SIZE)


def publish_audit_event(event: AuditEvent) -> None:
    global _sequence
    with _lock:
        _sequence += 1
        _ring.append((_sequence, event))


def events_since(cursor: int) -> tuple[list[AuditEvent], int]:
    normalized_cursor = max(0, int(cursor))
    with _lock:
        events = [event for seq, event in _ring if seq > normalized_cursor]
        return events, _sequence


def _format_sse_event(event: AuditEvent) -> str:
    return f"data: {json.dumps(asdict(event), ensure_ascii=True)}\n\n"


def reset_audit_events_state() -> None:
    global _sequence
    with _lock:
        _sequence = 0
        _ring.clear()
