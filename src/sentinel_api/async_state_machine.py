"""Compatibility shim for async state-machine primitives.

This module preserves existing imports during staged package extraction.
Prefer importing from `sentinel_core.async_state_machine` for new code.
"""

from sentinel_core.async_state_machine import (  # noqa: F401
    APPEAL_ALLOWED_TRANSITIONS,
    APPEAL_STATES,
    PROPOSAL_ALLOWED_TRANSITIONS,
    PROPOSAL_STATES,
    QUEUE_ALLOWED_TRANSITIONS,
    QUEUE_STATES,
    InvalidStateTransition,
    TransitionResult,
    validate_appeal_transition,
    validate_proposal_transition,
    validate_queue_transition,
)
