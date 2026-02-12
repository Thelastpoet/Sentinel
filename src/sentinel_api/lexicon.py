"""Compatibility shim for lexicon package extraction."""

import sys

from sentinel_lexicon import lexicon as _impl

sys.modules[__name__] = _impl
