"""Compatibility shim for core model types.

This module preserves existing imports during staged package extraction.
Prefer importing from `sentinel_core.models` for new code.
"""

from sentinel_core.models import (  # noqa: F401
    Action,
    ErrorResponse,
    EvidenceItem,
    EvidenceType,
    Label,
    LanguageSpan,
    MetricsResponse,
    ModerationContext,
    ModerationRequest,
    ModerationResponse,
    ReasonCode,
)
