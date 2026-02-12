from __future__ import annotations

import math


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if q <= 0:
        return min(values)
    if q >= 1:
        return max(values)
    ordered = sorted(values)
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[index]


def summarize_latency(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        raise ValueError("latencies_ms must not be empty")
    count = float(len(latencies_ms))
    return {
        "count": count,
        "min_ms": min(latencies_ms),
        "mean_ms": sum(latencies_ms) / count,
        "p95_ms": percentile(latencies_ms, 0.95),
        "max_ms": max(latencies_ms),
    }
