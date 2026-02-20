"""Compatibility shim for DB pooling.

The pool singleton lives in `sentinel_db.pool` so non-API packages can use pooling
without importing from `sentinel_api`.
"""

from __future__ import annotations

from sentinel_db.pool import close_pool, get_pool, peek_pool

__all__ = ["get_pool", "peek_pool", "close_pool"]
