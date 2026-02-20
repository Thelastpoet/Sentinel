from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from sentinel_api.audit_events import reset_audit_events_state
from sentinel_api.main import app
from sentinel_api.metrics import metrics
from sentinel_core.policy_config import set_runtime_phase_override

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTINEL_DATABASE_URL", raising=False)
    monkeypatch.delenv("SENTINEL_ELECTORAL_PHASE", raising=False)
    metrics.reset()
    set_runtime_phase_override(None)
    reset_audit_events_state()


def _set_registry(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]) -> None:
    monkeypatch.setenv("SENTINEL_OAUTH_TOKENS_JSON", json.dumps(payload))


def test_internal_queue_metrics_requires_bearer_token() -> None:
    response = client.get("/internal/monitoring/queue/metrics")
    assert response.status_code == 401
    payload = response.json()
    assert payload["error_code"] == "HTTP_401"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_internal_queue_metrics_rejects_missing_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-read-admin-only": {
                "client_id": "admin-reader",
                "scopes": ["admin:proposal:read"],
            }
        },
    )
    response = client.get(
        "/internal/monitoring/queue/metrics",
        headers={"Authorization": "Bearer token-read-admin-only"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error_code"] == "HTTP_403"
    assert "internal:queue:read" in payload["message"]


def test_internal_queue_metrics_allows_required_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-queue-read": {
                "client_id": "queue-reader",
                "scopes": ["internal:queue:read"],
            }
        },
    )
    response = client.get(
        "/internal/monitoring/queue/metrics",
        headers={"Authorization": "Bearer token-queue-read"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["actor_client_id"] == "queue-reader"
    assert "queue_depth_by_priority" in payload
    assert "sla_breach_count_by_priority" in payload


def test_admin_permissions_requires_read_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-review-only": {
                "client_id": "proposal-reviewer",
                "scopes": ["admin:proposal:review"],
            }
        },
    )
    response = client.get(
        "/admin/release-proposals/permissions",
        headers={"Authorization": "Bearer token-review-only"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error_code"] == "HTTP_403"
    assert "admin:proposal:read" in payload["message"]


def test_admin_review_accepts_review_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-review": {
                "client_id": "proposal-reviewer",
                "scopes": ["admin:proposal:review", "admin:proposal:read"],
            }
        },
    )
    response = client.post(
        "/admin/release-proposals/42/review",
        headers={"Authorization": "Bearer token-review"},
        json={"action": "approve", "rationale": "meets policy"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal_id"] == 42
    assert payload["action"] == "approve"
    assert payload["actor"] == "proposal-reviewer"
    assert payload["status"] == "accepted"


def test_admin_appeals_requires_read_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-proposal-only": {
                "client_id": "proposal-reviewer",
                "scopes": ["admin:proposal:read", "admin:proposal:review"],
            }
        },
    )
    response = client.get(
        "/admin/appeals",
        headers={"Authorization": "Bearer token-proposal-only"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error_code"] == "HTTP_403"
    assert "admin:appeal:read" in payload["message"]


def test_admin_appeals_allows_read_scope(monkeypatch: pytest.MonkeyPatch) -> None:
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
        "/admin/appeals",
        headers={"Authorization": "Bearer token-appeal-read"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] >= 0
    assert "items" in payload


def test_transparency_report_requires_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-appeal-read-only": {
                "client_id": "appeal-reader",
                "scopes": ["admin:appeal:read"],
            }
        },
    )
    response = client.get(
        "/admin/transparency/reports/appeals",
        headers={"Authorization": "Bearer token-appeal-read-only"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error_code"] == "HTTP_403"
    assert "admin:transparency:read" in payload["message"]


def test_transparency_export_allows_export_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-transparency-export": {
                "client_id": "transparency-exporter",
                "scopes": ["admin:transparency:export"],
            }
        },
    )
    response = client.get(
        "/admin/transparency/exports/appeals",
        headers={"Authorization": "Bearer token-transparency-export"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "records" in payload


def test_admin_policy_phase_requires_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-proposal-reader": {
                "client_id": "proposal-reader",
                "scopes": ["admin:proposal:read"],
            }
        },
    )
    response = client.post(
        "/admin/policy/phase",
        headers={"Authorization": "Bearer token-proposal-reader"},
        json={"phase": "voting_day"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error_code"] == "HTTP_403"
    assert "admin:policy:write" in payload["message"]


def test_admin_policy_phase_update_sets_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-policy-writer": {
                "client_id": "policy-writer",
                "scopes": ["admin:policy:write"],
            }
        },
    )
    monkeypatch.setenv("SENTINEL_ELECTORAL_PHASE", "campaign")

    response = client.post(
        "/admin/policy/phase",
        headers={"Authorization": "Bearer token-policy-writer"},
        json={"phase": "voting_day"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_phase"] == "voting_day"
    assert payload["actor"] == "policy-writer"

    response = client.post(
        "/admin/policy/phase",
        headers={"Authorization": "Bearer token-policy-writer"},
        json={"phase": None},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_phase"] == "campaign"


def test_admin_audit_stream_requires_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-appeal-reader": {
                "client_id": "appeal-reader",
                "scopes": ["admin:appeal:read"],
            }
        },
    )
    response = client.get(
        "/admin/audit/stream",
        headers={"Authorization": "Bearer token-appeal-reader"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error_code"] == "HTTP_403"
    assert "admin:transparency:read" in payload["message"]


def test_internal_queue_metrics_accepts_valid_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "test-secret-which-is-long-enough-32+"
    monkeypatch.setenv("SENTINEL_OAUTH_JWT_SECRET", secret)
    monkeypatch.delenv("SENTINEL_OAUTH_TOKENS_JSON", raising=False)
    token = jwt.encode(
        {
            "sub": "jwt-queue-reader",
            "scope": "internal:queue:read",
            "exp": datetime.now(tz=UTC) + timedelta(minutes=5),
        },
        secret,
        algorithm="HS256",
    )
    response = client.get(
        "/internal/monitoring/queue/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["actor_client_id"] == "jwt-queue-reader"


def test_internal_queue_metrics_rejects_expired_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "test-secret-which-is-long-enough-32+"
    monkeypatch.setenv("SENTINEL_OAUTH_JWT_SECRET", secret)
    token = jwt.encode(
        {
            "sub": "expired-reader",
            "scope": "internal:queue:read",
            "exp": datetime.now(tz=UTC) - timedelta(minutes=1),
        },
        secret,
        algorithm="HS256",
    )
    response = client.get(
        "/internal/monitoring/queue/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
