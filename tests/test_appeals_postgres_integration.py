from __future__ import annotations

import os
from uuid import uuid4

import pytest

from sentinel_api.appeals import (
    AdminAppealCreateRequest,
    AdminAppealTransitionRequest,
    get_appeals_runtime,
)


def _integration_db_url() -> str | None:
    return os.getenv("SENTINEL_INTEGRATION_DB_URL")


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_postgres_appeal_flow_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    monkeypatch.setenv("SENTINEL_DATABASE_URL", db_url)
    runtime = get_appeals_runtime()

    suffix = uuid4().hex[:10]
    created = runtime.create_appeal(
        AdminAppealCreateRequest(
            original_decision_id=f"decision-{suffix}",
            request_id=f"request-{suffix}",
            original_action="REVIEW",
            original_reason_codes=["R_DISINFO_NARRATIVE_SIMILARITY"],
            original_model_version="sentinel-multi-v2",
            original_lexicon_version="hatelex-v2.1",
            original_policy_version="policy-2026.10",
            original_pack_versions={"en": "pack-en-0.1"},
            rationale="integration appeal for regression coverage",
        ),
        submitted_by="integration-suite",
    )

    assert created.status == "submitted"
    appeal_id = created.id

    triaged = runtime.transition_appeal(
        appeal_id=appeal_id,
        payload=AdminAppealTransitionRequest(
            to_status="triaged",
            rationale="triage complete",
        ),
        actor="integration-reviewer",
    )
    assert triaged.status == "triaged"

    review = runtime.transition_appeal(
        appeal_id=appeal_id,
        payload=AdminAppealTransitionRequest(
            to_status="in_review",
            rationale="evidence reassessment started",
        ),
        actor="integration-reviewer",
    )
    assert review.status == "in_review"

    resolved = runtime.transition_appeal(
        appeal_id=appeal_id,
        payload=AdminAppealTransitionRequest(
            to_status="resolved_modified",
            rationale="updated reason-code mapping",
            resolution_code="APPEAL_MODIFIED_MAPPING",
            resolution_reason_codes=["R_ALLOW_NO_POLICY_MATCH"],
        ),
        actor="integration-reviewer",
    )
    assert resolved.status == "resolved_modified"
    assert resolved.resolution_code == "APPEAL_MODIFIED_MAPPING"

    listed = runtime.list_appeals(status="resolved_modified", request_id=None, limit=100)
    assert any(item.id == appeal_id for item in listed.items)

    reconstruction = runtime.reconstruct(appeal_id=appeal_id)
    assert reconstruction.appeal.id == appeal_id
    assert reconstruction.appeal.original_decision_id == f"decision-{suffix}"
    assert [event.to_status for event in reconstruction.timeline] == [
        "submitted",
        "triaged",
        "in_review",
        "resolved_modified",
    ]
