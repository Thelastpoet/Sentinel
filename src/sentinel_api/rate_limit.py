from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

try:
    from limits import RateLimitItemPerMinute
    from limits.storage import storage_from_string
    from limits.strategies import MovingWindowRateLimiter
except Exception:  # pragma: no cover - optional runtime dependency
    RateLimitItemPerMinute = None  # type: ignore[assignment]
    storage_from_string = None  # type: ignore[assignment]
    MovingWindowRateLimiter = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


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
    storage_uri = os.getenv("SENTINEL_RATE_LIMIT_STORAGE_URI") or os.getenv("SENTINEL_REDIS_URL")
    if storage_uri:
        limiter = _build_limits_rate_limiter(per_minute=per_minute, storage_uri=storage_uri)
        if limiter is not None:
            return limiter
    return InMemoryRateLimiter(per_minute=per_minute)


class LimitsRateLimiter(InMemoryRateLimiter):
    def __init__(self, per_minute: int, storage_uri: str) -> None:
        super().__init__(per_minute=per_minute)
        if (
            storage_from_string is None
            or MovingWindowRateLimiter is None
            or RateLimitItemPerMinute is None
        ):
            raise RuntimeError("limits library is unavailable")
        self.storage_uri = storage_uri
        self._storage = storage_from_string(storage_uri)
        self._limiter = MovingWindowRateLimiter(self._storage)
        self._rate_limit_item_cls: Any = RateLimitItemPerMinute

    def check(self, key: str) -> RateLimitDecision:
        # Preserve existing response contract while shifting enforcement to
        # distributed limits storage (Redis/memcached/etc.).
        now = time.time()
        normalized_key = f"sentinel-rate-limit:{key}"
        item = self._rate_limit_item_cls(self.per_minute)
        try:
            allowed = bool(self._limiter.hit(item, normalized_key))
            window = self._limiter.get_window_stats(item, normalized_key)
        except Exception as exc:  # pragma: no cover - network/storage failures
            logger.warning(
                "distributed rate limiter unavailable; using in-memory fallback: %s",
                exc,
            )
            return super().check(key)

        reset_after = max(1, int(window.reset_time - now))
        remaining = max(0, int(window.remaining))
        if not allowed:
            return RateLimitDecision(
                allowed=False,
                limit=self.per_minute,
                remaining=0,
                reset_after_seconds=reset_after,
                retry_after_seconds=reset_after,
            )
        return RateLimitDecision(
            allowed=True,
            limit=self.per_minute,
            remaining=remaining,
            reset_after_seconds=reset_after,
        )

    def reset(self) -> None:
        # Limits backends do not provide a safe global reset primitive across
        # all storage backends. Keep local fallback state reset for test calls.
        super().reset()


def _build_limits_rate_limiter(*, per_minute: int, storage_uri: str) -> LimitsRateLimiter | None:
    try:
        return LimitsRateLimiter(per_minute=per_minute, storage_uri=storage_uri)
    except Exception as exc:
        logger.warning(
            "failed to initialize distributed rate limiter at %s; using in-memory: %s",
            storage_uri,
            exc,
        )
        return None
