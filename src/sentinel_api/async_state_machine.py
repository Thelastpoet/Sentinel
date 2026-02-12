from __future__ import annotations

from dataclasses import dataclass


QUEUE_STATES: set[str] = {
    "queued",
    "processing",
    "clustered",
    "proposed",
    "dropped",
    "error",
}

PROPOSAL_STATES: set[str] = {
    "draft",
    "in_review",
    "needs_revision",
    "approved",
    "promoted",
    "rejected",
}

QUEUE_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"processing", "dropped"},
    "processing": {"clustered", "error"},
    "clustered": {"proposed", "dropped"},
    "proposed": set(),
    "dropped": set(),
    "error": {"queued", "dropped"},
}

PROPOSAL_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"in_review", "rejected"},
    "in_review": {"approved", "rejected", "needs_revision"},
    "needs_revision": {"in_review", "rejected"},
    "approved": {"promoted", "rejected"},
    "promoted": set(),
    "rejected": set(),
}


@dataclass(frozen=True)
class TransitionResult:
    entity: str
    from_state: str
    to_state: str


class InvalidStateTransition(ValueError):
    pass


def _normalize(state: str) -> str:
    return state.strip().lower()


def validate_queue_transition(from_state: str, to_state: str) -> TransitionResult:
    source = _normalize(from_state)
    target = _normalize(to_state)
    if source not in QUEUE_STATES:
        raise InvalidStateTransition(f"unknown queue state: {from_state}")
    if target not in QUEUE_STATES:
        raise InvalidStateTransition(f"unknown queue state: {to_state}")
    if target not in QUEUE_ALLOWED_TRANSITIONS[source]:
        raise InvalidStateTransition(f"queue transition not allowed: {source} -> {target}")
    return TransitionResult(entity="queue", from_state=source, to_state=target)


def validate_proposal_transition(from_state: str, to_state: str) -> TransitionResult:
    source = _normalize(from_state)
    target = _normalize(to_state)
    if source not in PROPOSAL_STATES:
        raise InvalidStateTransition(f"unknown proposal state: {from_state}")
    if target not in PROPOSAL_STATES:
        raise InvalidStateTransition(f"unknown proposal state: {to_state}")
    if target not in PROPOSAL_ALLOWED_TRANSITIONS[source]:
        raise InvalidStateTransition(
            f"proposal transition not allowed: {source} -> {target}"
        )
    return TransitionResult(entity="proposal", from_state=source, to_state=target)
