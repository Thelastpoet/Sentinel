"""Compatibility shim for lexicon package extraction."""

import sys

from sentinel_lexicon import hot_triggers as _impl

sys.modules[__name__] = _impl
