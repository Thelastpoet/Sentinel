from __future__ import annotations

import sys

from sentinel_core import eval_harness as _impl

sys.modules[__name__] = _impl

