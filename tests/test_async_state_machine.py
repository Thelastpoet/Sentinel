from __future__ import annotations

import pytest

from sentinel_api.async_state_machine import (
    InvalidStateTransition,
    validate_appeal_transition,
    validate_model_artifact_transition,
    validate_proposal_transition,
    validate_queue_transition,
)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("queued", "processing"),
        ("queued", "dropped"),
        ("processing", "clustered"),
        ("processing", "error"),
        ("clustered", "proposed"),
        ("clustered", "dropped"),
        ("error", "queued"),
        ("error", "dropped"),
    ],
)
def test_validate_queue_transition_allows_expected_paths(source: str, target: str) -> None:
    result = validate_queue_transition(source, target)
    assert result.entity == "queue"
    assert result.from_state == source
    assert result.to_state == target


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("queued", "queued"),
        ("proposed", "queued"),
        ("dropped", "processing"),
        ("processing", "proposed"),
    ],
)
def test_validate_queue_transition_rejects_invalid_paths(source: str, target: str) -> None:
    with pytest.raises(InvalidStateTransition):
        validate_queue_transition(source, target)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("draft", "in_review"),
        ("draft", "rejected"),
        ("in_review", "approved"),
        ("in_review", "rejected"),
        ("in_review", "needs_revision"),
        ("needs_revision", "in_review"),
        ("needs_revision", "rejected"),
        ("approved", "promoted"),
        ("approved", "rejected"),
    ],
)
def test_validate_proposal_transition_allows_expected_paths(source: str, target: str) -> None:
    result = validate_proposal_transition(source, target)
    assert result.entity == "proposal"
    assert result.from_state == source
    assert result.to_state == target


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("draft", "promoted"),
        ("rejected", "in_review"),
        ("promoted", "rejected"),
        ("approved", "draft"),
    ],
)
def test_validate_proposal_transition_rejects_invalid_paths(source: str, target: str) -> None:
    with pytest.raises(InvalidStateTransition):
        validate_proposal_transition(source, target)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("submitted", "triaged"),
        ("submitted", "rejected_invalid"),
        ("triaged", "in_review"),
        ("triaged", "rejected_invalid"),
        ("in_review", "resolved_upheld"),
        ("in_review", "resolved_reversed"),
        ("in_review", "resolved_modified"),
    ],
)
def test_validate_appeal_transition_allows_expected_paths(source: str, target: str) -> None:
    result = validate_appeal_transition(source, target)
    assert result.entity == "appeal"
    assert result.from_state == source
    assert result.to_state == target


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("submitted", "in_review"),
        ("triaged", "resolved_reversed"),
        ("resolved_upheld", "resolved_modified"),
        ("rejected_invalid", "triaged"),
    ],
)
def test_validate_appeal_transition_rejects_invalid_paths(source: str, target: str) -> None:
    with pytest.raises(InvalidStateTransition):
        validate_appeal_transition(source, target)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("draft", "validated"),
        ("draft", "revoked"),
        ("validated", "active"),
        ("validated", "deprecated"),
        ("validated", "revoked"),
        ("active", "deprecated"),
        ("active", "revoked"),
        ("deprecated", "active"),
        ("deprecated", "revoked"),
    ],
)
def test_validate_model_artifact_transition_allows_expected_paths(
    source: str,
    target: str,
) -> None:
    result = validate_model_artifact_transition(source, target)
    assert result.entity == "model_artifact"
    assert result.from_state == source
    assert result.to_state == target


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("draft", "active"),
        ("active", "validated"),
        ("revoked", "active"),
        ("revoked", "draft"),
    ],
)
def test_validate_model_artifact_transition_rejects_invalid_paths(
    source: str,
    target: str,
) -> None:
    with pytest.raises(InvalidStateTransition):
        validate_model_artifact_transition(source, target)


@pytest.mark.parametrize(
    ("validator", "source", "target"),
    [
        (validate_queue_transition, "unknown", "queued"),
        (validate_queue_transition, "queued", "unknown"),
        (validate_proposal_transition, "unknown", "draft"),
        (validate_proposal_transition, "draft", "unknown"),
        (validate_appeal_transition, "unknown", "submitted"),
        (validate_appeal_transition, "submitted", "unknown"),
        (validate_model_artifact_transition, "unknown", "draft"),
        (validate_model_artifact_transition, "draft", "unknown"),
    ],
)
def test_unknown_states_raise(validator, source: str, target: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(InvalidStateTransition):
        validator(source, target)
