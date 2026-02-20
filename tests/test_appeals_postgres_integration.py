from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
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
            original_policy_version="policy-2026.11",
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


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_reversed_appeal_creates_draft_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
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
            original_policy_version="policy-2026.11",
            original_pack_versions={"en": "pack-en-0.1"},
            rationale="proposal integration appeal",
        ),
        submitted_by="integration-suite",
    )
    resolved = runtime.transition_appeal(
        appeal_id=created.id,
        payload=AdminAppealTransitionRequest(
            to_status="resolved_reversed",
            rationale="reversed",
            resolution_code="APPEAL_REVERSED",
            resolution_reason_codes=["R_ALLOW_NO_POLICY_MATCH"],
        ),
        actor="integration-reviewer",
    )
    assert resolved.status == "resolved_reversed"

    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, status, proposal_type, evidence
                FROM release_proposals
                WHERE proposed_by = %s
                ORDER BY id DESC
                LIMIT 5
                """,
                ("integration-reviewer",),
            )
            rows = cur.fetchall()
    assert any(
        row[1] == "draft"
        and row[2] == "lexicon"
        and str(resolved.id) in str(row[0])
        and str(resolved.resolution_code) in str(row[0])
        for row in rows
    )


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_upheld_appeal_no_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
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
            original_policy_version="policy-2026.11",
            original_pack_versions={"en": "pack-en-0.1"},
            rationale="upheld integration appeal",
        ),
        submitted_by="integration-suite",
    )
    resolved = runtime.transition_appeal(
        appeal_id=created.id,
        payload=AdminAppealTransitionRequest(
            to_status="resolved_upheld",
            rationale="upheld",
            resolution_code="APPEAL_UPHELD",
        ),
        actor="integration-reviewer",
    )
    assert resolved.status == "resolved_upheld"

    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(1) FROM release_proposals WHERE title LIKE %s",
                (f"%appeal #{created.id}:%",),
            )
            row = cur.fetchone()
    assert row is not None
    assert int(row[0]) == 0


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_training_sample_written_on_reversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    monkeypatch.setenv("SENTINEL_DATABASE_URL", db_url)
    out_path = tmp_path / "train.jsonl"
    monkeypatch.setenv("SENTINEL_TRAINING_DATA_PATH", str(out_path))
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
            original_policy_version="policy-2026.11",
            original_pack_versions={"en": "pack-en-0.1"},
            rationale="training integration appeal",
        ),
        submitted_by="integration-suite",
    )
    resolved = runtime.transition_appeal(
        appeal_id=created.id,
        payload=AdminAppealTransitionRequest(
            to_status="resolved_modified",
            rationale="modified",
            resolution_code="APPEAL_MODIFIED",
            resolution_reason_codes=["R_ALLOW_NO_POLICY_MATCH"],
        ),
        actor="integration-reviewer",
    )
    assert resolved.status == "resolved_modified"
    assert out_path.exists()
    lines = [line for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["appeal_id"] == created.id
    assert "text" not in record
