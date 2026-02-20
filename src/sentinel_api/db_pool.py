from __future__ import annotations

import logging
from threading import Lock
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from psycopg_pool import ConnectionPool
else:  # pragma: no cover
    ConnectionPool = object  # type: ignore[assignment]

_pool: ConnectionPool | None = None
_pool_lock = Lock()
_pool_import_failed: bool = False


def get_pool(database_url: str) -> ConnectionPool | None:
    """Return a singleton psycopg connection pool for the given DB URL.

    Pooling is optional: if `psycopg_pool` is not available, this returns None.
    """
    global _pool
    if _pool is not None:
        return _pool

    normalized_url = database_url.strip()
    if not normalized_url:
        return None

    with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            from psycopg_pool import ConnectionPool as _ConnectionPool
        except ImportError:
            global _pool_import_failed
            if not _pool_import_failed:
                logger.warning("psycopg_pool is not installed; DB pooling disabled")
                _pool_import_failed = True
            _pool = None
            return None

        _pool = _ConnectionPool(
            conninfo=normalized_url,
            min_size=2,
            max_size=10,
            open=True,
        )
        return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        pool = _pool
        _pool = None
    if pool is None:
        return
    try:
        pool.close()
    except Exception as exc:  # pragma: no cover - defensive shutdown
        logger.warning("failed to close DB pool cleanly: %s", exc)
