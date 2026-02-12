from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from sentinel_api.appeals import reset_appeals_runtime_state
from sentinel_api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_appeals_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTINEL_DATABASE_URL", raising=False)
    reset_appeals_runtime_state()


def _set_registry(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]) -> None:
    monkeypatch.setenv("SENTINEL_OAUTH_TOKENS_JSON", json.dumps(payload))


def _appeal_payload() -> dict[str, object]:
    return {
        "original_decision_id": "dec-123",
        "request_id": "req-123",
        "original_action": "BLOCK",
        "original_reason_codes": ["R_INCITE_CALL_TO_HARM"],
        "original_model_version": "sentinel-multi-v2",
        "original_lexicon_version": "hatelex-v2.1",
        "original_policy_version": "policy-2026.10",
        "original_pack_versions": {"en": "pack-en-0.1"},
        "rationale": "content owner disputes context",
    }


def test_admin_appeals_create_requires_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-read-only": {
                "client_id": "appeal-reader",
                "scopes": ["admin:appeal:read"],
            }
        },
    )
    response = client.post(
        "/admin/appeals",
        headers={"Authorization": "Bearer token-read-only"},
        json=_appeal_payload(),
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error_code"] == "HTTP_403"
    assert "admin:appeal:write" in payload["message"]


def test_admin_appeals_end_to_end_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-appeal-admin": {
                "client_id": "appeal-admin",
                "scopes": ["admin:appeal:read", "admin:appeal:write"],
            }
        },
    )

    create_response = client.post(
        "/admin/appeals",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json=_appeal_payload(),
    )
    assert create_response.status_code == 200
    created = create_response.json()
    appeal_id = created["id"]
    assert created["status"] == "submitted"
    assert created["submitted_by"] == "appeal-admin"

    list_response = client.get(
        "/admin/appeals?status=submitted",
        headers={"Authorization": "Bearer token-appeal-admin"},
    )
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total_count"] >= 1
    assert listed["items"][0]["id"] == appeal_id

    triaged = client.post(
        f"/admin/appeals/{appeal_id}/transition",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json={"to_status": "triaged", "rationale": "initial screening complete"},
    )
    assert triaged.status_code == 200
    assert triaged.json()["status"] == "triaged"

    in_review = client.post(
        f"/admin/appeals/{appeal_id}/transition",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json={"to_status": "in_review", "rationale": "assigned to reviewer"},
    )
    assert in_review.status_code == 200
    assert in_review.json()["status"] == "in_review"

    resolved = client.post(
        f"/admin/appeals/{appeal_id}/transition",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json={
            "to_status": "resolved_reversed",
            "rationale": "context shows non-incitement",
            "resolution_code": "APPEAL_REVERSED_CONTEXT",
            "resolution_reason_codes": ["R_ALLOW_NO_POLICY_MATCH"],
        },
    )
    assert resolved.status_code == 200
    resolved_payload = resolved.json()
    assert resolved_payload["status"] == "resolved_reversed"
    assert resolved_payload["resolution_code"] == "APPEAL_REVERSED_CONTEXT"
    assert resolved_payload["resolution_reason_codes"] == ["R_ALLOW_NO_POLICY_MATCH"]

    reconstruct = client.get(
        f"/admin/appeals/{appeal_id}/reconstruct",
        headers={"Authorization": "Bearer token-appeal-admin"},
    )
    assert reconstruct.status_code == 200
    reconstruction_payload = reconstruct.json()
    assert reconstruction_payload["appeal"]["id"] == appeal_id
    assert reconstruction_payload["artifact_versions"]["model"] == "sentinel-multi-v2"
    assert reconstruction_payload["resolution"]["status"] == "resolved_reversed"
    assert [event["to_status"] for event in reconstruction_payload["timeline"]] == [
        "submitted",
        "triaged",
        "in_review",
        "resolved_reversed",
    ]


def test_admin_appeals_rejects_invalid_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-appeal-admin": {
                "client_id": "appeal-admin",
                "scopes": ["admin:appeal:read", "admin:appeal:write"],
            }
        },
    )

    create_response = client.post(
        "/admin/appeals",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json=_appeal_payload(),
    )
    assert create_response.status_code == 200
    appeal_id = create_response.json()["id"]

    invalid_transition = client.post(
        f"/admin/appeals/{appeal_id}/transition",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json={"to_status": "resolved_upheld", "resolution_code": "APPEAL_UPHELD"},
    )
    assert invalid_transition.status_code == 400
    payload = invalid_transition.json()
    assert payload["error_code"] == "HTTP_400"
    assert "appeal transition not allowed" in payload["message"]


def test_admin_appeals_resolution_payload_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-appeal-admin": {
                "client_id": "appeal-admin",
                "scopes": ["admin:appeal:read", "admin:appeal:write"],
            }
        },
    )
    create_response = client.post(
        "/admin/appeals",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json=_appeal_payload(),
    )
    assert create_response.status_code == 200
    appeal_id = create_response.json()["id"]

    triaged = client.post(
        f"/admin/appeals/{appeal_id}/transition",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json={"to_status": "triaged"},
    )
    assert triaged.status_code == 200
    in_review = client.post(
        f"/admin/appeals/{appeal_id}/transition",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json={"to_status": "in_review"},
    )
    assert in_review.status_code == 200
    missing_reason_codes = client.post(
        f"/admin/appeals/{appeal_id}/transition",
        headers={"Authorization": "Bearer token-appeal-admin"},
        json={
            "to_status": "resolved_reversed",
            "resolution_code": "APPEAL_REVERSED_CONTEXT",
        },
    )
    assert missing_reason_codes.status_code == 400
    payload = missing_reason_codes.json()
    assert payload["error_code"] == "HTTP_400"
    assert "resolution_reason_codes" in payload["message"]


def test_admin_appeals_reconstruct_missing_record_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-appeal-read": {
                "client_id": "appeal-reader",
                "scopes": ["admin:appeal:read"],
            }
        },
    )
    response = client.get(
        "/admin/appeals/9999/reconstruct",
        headers={"Authorization": "Bearer token-appeal-read"},
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["error_code"] == "HTTP_404"
