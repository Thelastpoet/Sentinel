"""Compatibility shim for langpack package extraction."""

import sys

from sentinel_langpack import registry as _impl

sys.modules[__name__] = _impl

