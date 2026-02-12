from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int
    retry_after_seconds: int | None = None


class InMemoryRateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self.window_seconds = 60
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def _cleanup(self, bucket: deque[float], now: float) -> None:
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

    def check(self, key: str) -> RateLimitDecision:
        now = time.time()
        bucket = self._events[key]
        self._cleanup(bucket, now)

        if not bucket:
            reset_after = self.window_seconds
        else:
            reset_after = max(1, int(self.window_seconds - (now - bucket[0])))

        if len(bucket) >= self.per_minute:
            return RateLimitDecision(
                allowed=False,
                limit=self.per_minute,
                remaining=0,
                reset_after_seconds=reset_after,
                retry_after_seconds=reset_after,
            )

        bucket.append(now)
        remaining = max(self.per_minute - len(bucket), 0)
        reset_after = max(1, int(self.window_seconds - (now - bucket[0])))
        return RateLimitDecision(
            allowed=True,
            limit=self.per_minute,
            remaining=remaining,
            reset_after_seconds=reset_after,
        )

    def allow(self, key: str) -> bool:
        return self.check(key).allowed

    def reset(self) -> None:
        self._events.clear()


def build_rate_limiter() -> InMemoryRateLimiter:
    per_minute = int(os.getenv("SENTINEL_RATE_LIMIT_PER_MINUTE", "120"))
    return InMemoryRateLimiter(per_minute=per_minute)
