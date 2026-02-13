from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from sentinel_api.appeals import AdminAppealCreateRequest, get_appeals_runtime
from sentinel_api.transparency import get_transparency_runtime


def _integration_db_url() -> str | None:
    return os.getenv("SENTINEL_INTEGRATION_DB_URL")


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_transparency_export_and_report_with_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    monkeypatch.setenv("SENTINEL_DATABASE_URL", db_url)
    appeals_runtime = get_appeals_runtime()
    transparency_runtime = get_transparency_runtime()

    marker = datetime.now(tz=UTC)
    suffix = uuid4().hex[:10]
    created = appeals_runtime.create_appeal(
        AdminAppealCreateRequest(
            original_decision_id=f"decision-{suffix}",
            request_id=f"request-{suffix}",
            original_action="REVIEW",
            original_reason_codes=["R_DISINFO_NARRATIVE_SIMILARITY"],
            original_model_version="sentinel-multi-v2",
            original_lexicon_version="hatelex-v2.1",
            original_policy_version="policy-2026.11",
            original_pack_versions={"en": "pack-en-0.1"},
            rationale="transparency postgres integration artifact",
        ),
        submitted_by="integration-suite",
    )

    export_redacted = transparency_runtime.export_appeals_records(
        created_from=marker,
        created_to=None,
        limit=200,
        include_identifiers=False,
    )
    record_redacted = next(item for item in export_redacted.records if item.appeal_id == created.id)
    assert record_redacted.request_id is None
    assert record_redacted.original_decision_id is None

    export_full = transparency_runtime.export_appeals_records(
        created_from=marker,
        created_to=None,
        limit=200,
        include_identifiers=True,
    )
    record_full = next(item for item in export_full.records if item.appeal_id == created.id)
    assert record_full.request_id == f"request-{suffix}"
    assert record_full.original_decision_id == f"decision-{suffix}"

    report = transparency_runtime.build_appeals_report(
        created_from=marker,
        created_to=None,
    )
    assert report.total_appeals >= 1
    assert report.status_counts.get("submitted", 0) >= 1
