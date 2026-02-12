"""Compatibility shim for router package extraction."""

import sys

from sentinel_router import language_router as _impl

sys.modules[__name__] = _impl
