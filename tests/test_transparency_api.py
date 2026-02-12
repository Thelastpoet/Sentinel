from __future__ import annotations

import json

from fastapi.testclient import TestClient
import pytest

from sentinel_api.appeals import reset_appeals_runtime_state
from sentinel_api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_appeals_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTINEL_DATABASE_URL", raising=False)
    reset_appeals_runtime_state()


def _set_registry(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]) -> None:
    monkeypatch.setenv("SENTINEL_OAUTH_TOKENS_JSON", json.dumps(payload))


def _appeal_payload(*, suffix: str, reason_code: str) -> dict[str, object]:
    return {
        "original_decision_id": f"dec-{suffix}",
        "request_id": f"req-{suffix}",
        "original_action": "REVIEW",
        "original_reason_codes": [reason_code],
        "original_model_version": "sentinel-multi-v2",
        "original_lexicon_version": "hatelex-v2.1",
        "original_policy_version": "policy-2026.10",
        "original_pack_versions": {"en": "pack-en-0.1"},
        "rationale": "transparency testing artifact",
    }


def test_transparency_report_and_export_with_redaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-admin": {
                "client_id": "admin-ops",
                "scopes": [
                    "admin:appeal:read",
                    "admin:appeal:write",
                    "admin:transparency:read",
                    "admin:transparency:export",
                ],
            }
        },
    )

    created_one = client.post(
        "/admin/appeals",
        headers={"Authorization": "Bearer token-admin"},
        json=_appeal_payload(suffix="one", reason_code="R_DISINFO_NARRATIVE_SIMILARITY"),
    )
    assert created_one.status_code == 200
    appeal_id_one = created_one.json()["id"]

    created_two = client.post(
        "/admin/appeals",
        headers={"Authorization": "Bearer token-admin"},
        json=_appeal_payload(suffix="two", reason_code="R_ALLOW_NO_POLICY_MATCH"),
    )
    assert created_two.status_code == 200
    appeal_id_two = created_two.json()["id"]

    triaged_one = client.post(
        f"/admin/appeals/{appeal_id_one}/transition",
        headers={"Authorization": "Bearer token-admin"},
        json={"to_status": "triaged"},
    )
    assert triaged_one.status_code == 200
    in_review_one = client.post(
        f"/admin/appeals/{appeal_id_one}/transition",
        headers={"Authorization": "Bearer token-admin"},
        json={"to_status": "in_review"},
    )
    assert in_review_one.status_code == 200
    resolved_one = client.post(
        f"/admin/appeals/{appeal_id_one}/transition",
        headers={"Authorization": "Bearer token-admin"},
        json={
            "to_status": "resolved_reversed",
            "resolution_code": "APPEAL_REVERSED_CONTEXT",
            "resolution_reason_codes": ["R_ALLOW_NO_POLICY_MATCH"],
        },
    )
    assert resolved_one.status_code == 200
    triaged_two = client.post(
        f"/admin/appeals/{appeal_id_two}/transition",
        headers={"Authorization": "Bearer token-admin"},
        json={"to_status": "triaged"},
    )
    assert triaged_two.status_code == 200

    report = client.get(
        "/admin/transparency/reports/appeals",
        headers={"Authorization": "Bearer token-admin"},
    )
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["total_appeals"] == 2
    assert report_payload["resolved_appeals"] == 1
    assert report_payload["open_appeals"] == 1
    assert report_payload["resolution_counts"]["resolved_reversed"] == 1
    assert report_payload["resolution_counts"]["resolved_upheld"] == 0
    assert report_payload["resolution_counts"]["resolved_modified"] == 0
    assert report_payload["status_counts"]["triaged"] == 1

    export = client.get(
        "/admin/transparency/exports/appeals",
        headers={"Authorization": "Bearer token-admin"},
    )
    assert export.status_code == 200
    export_payload = export.json()
    assert export_payload["total_count"] == 2
    assert export_payload["include_identifiers"] is False
    assert export_payload["records"][0]["request_id"] is None
    assert export_payload["records"][0]["original_decision_id"] is None


def test_transparency_export_include_identifiers_requires_extra_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-export-no-identifiers": {
                "client_id": "exporter",
                "scopes": [
                    "admin:appeal:read",
                    "admin:appeal:write",
                    "admin:transparency:export",
                ],
            },
            "token-export-identifiers": {
                "client_id": "exporter-identifiers",
                "scopes": [
                    "admin:appeal:read",
                    "admin:appeal:write",
                    "admin:transparency:export",
                    "admin:transparency:identifiers",
                ],
            },
        },
    )

    created = client.post(
        "/admin/appeals",
        headers={"Authorization": "Bearer token-export-no-identifiers"},
        json=_appeal_payload(
            suffix="with-identifiers", reason_code="R_DISINFO_NARRATIVE_SIMILARITY"
        ),
    )
    assert created.status_code == 200

    blocked = client.get(
        "/admin/transparency/exports/appeals?include_identifiers=true",
        headers={"Authorization": "Bearer token-export-no-identifiers"},
    )
    assert blocked.status_code == 403
    blocked_payload = blocked.json()
    assert blocked_payload["error_code"] == "HTTP_403"
    assert "admin:transparency:identifiers" in blocked_payload["message"]

    allowed = client.get(
        "/admin/transparency/exports/appeals?include_identifiers=true",
        headers={"Authorization": "Bearer token-export-identifiers"},
    )
    assert allowed.status_code == 200
    allowed_payload = allowed.json()
    assert allowed_payload["include_identifiers"] is True
    assert allowed_payload["total_count"] == 1
    assert allowed_payload["records"][0]["request_id"] == "req-with-identifiers"
    assert (
        allowed_payload["records"][0]["original_decision_id"]
        == "dec-with-identifiers"
    )


def test_transparency_datetime_query_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-transparency-read": {
                "client_id": "reader",
                "scopes": ["admin:transparency:read"],
            }
        },
    )
    response = client.get(
        "/admin/transparency/reports/appeals?created_from=not-a-datetime",
        headers={"Authorization": "Bearer token-transparency-read"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "HTTP_400"
    assert "created_from must be ISO-8601 datetime" in payload["message"]


def test_transparency_datetime_query_accepts_z_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-transparency-read": {
                "client_id": "reader",
                "scopes": ["admin:transparency:read"],
            }
        },
    )
    response = client.get(
        "/admin/transparency/reports/appeals?created_from=2026-02-12T00:00:00Z",
        headers={"Authorization": "Bearer token-transparency-read"},
    )
    assert response.status_code == 200
