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

APPEAL_STATES: set[str] = {
    "submitted",
    "triaged",
    "in_review",
    "rejected_invalid",
    "resolved_upheld",
    "resolved_reversed",
    "resolved_modified",
}

MODEL_ARTIFACT_STATES: set[str] = {
    "draft",
    "validated",
    "active",
    "deprecated",
    "revoked",
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

APPEAL_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"triaged", "rejected_invalid"},
    "triaged": {"in_review", "rejected_invalid"},
    "in_review": {"resolved_upheld", "resolved_reversed", "resolved_modified"},
    "rejected_invalid": set(),
    "resolved_upheld": set(),
    "resolved_reversed": set(),
    "resolved_modified": set(),
}

MODEL_ARTIFACT_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"validated", "revoked"},
    "validated": {"active", "deprecated", "revoked"},
    "active": {"deprecated", "revoked"},
    "deprecated": {"active", "revoked"},
    "revoked": set(),
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
        raise InvalidStateTransition(f"proposal transition not allowed: {source} -> {target}")
    return TransitionResult(entity="proposal", from_state=source, to_state=target)


def validate_appeal_transition(from_state: str, to_state: str) -> TransitionResult:
    source = _normalize(from_state)
    target = _normalize(to_state)
    if source not in APPEAL_STATES:
        raise InvalidStateTransition(f"unknown appeal state: {from_state}")
    if target not in APPEAL_STATES:
        raise InvalidStateTransition(f"unknown appeal state: {to_state}")
    if target not in APPEAL_ALLOWED_TRANSITIONS[source]:
        raise InvalidStateTransition(f"appeal transition not allowed: {source} -> {target}")
    return TransitionResult(entity="appeal", from_state=source, to_state=target)


def validate_model_artifact_transition(from_state: str, to_state: str) -> TransitionResult:
    source = _normalize(from_state)
    target = _normalize(to_state)
    if source not in MODEL_ARTIFACT_STATES:
        raise InvalidStateTransition(f"unknown model artifact state: {from_state}")
    if target not in MODEL_ARTIFACT_STATES:
        raise InvalidStateTransition(f"unknown model artifact state: {to_state}")
    if target not in MODEL_ARTIFACT_ALLOWED_TRANSITIONS[source]:
        raise InvalidStateTransition(f"model artifact transition not allowed: {source} -> {target}")
    return TransitionResult(entity="model_artifact", from_state=source, to_state=target)
