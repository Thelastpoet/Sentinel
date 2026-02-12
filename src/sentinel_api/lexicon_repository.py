"""Compatibility shim for lexicon package extraction."""

import sys

from sentinel_lexicon import lexicon_repository as _impl

sys.modules[__name__] = _impl
