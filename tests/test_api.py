from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel_api.main import app, rate_limiter
from sentinel_api.metrics import metrics

client = TestClient(app)
TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def reset_rate_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_API_KEY", TEST_API_KEY)
    rate_limiter.reset()
    metrics.reset()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_moderate_requires_api_key() -> None:
    response = client.post("/v1/moderate", json={"text": "hello world"})
    assert response.status_code == 401
    payload = response.json()
    assert payload["error_code"] == "HTTP_401"
    assert "message" in payload
    assert "request_id" in payload
    assert response.headers["X-Request-ID"] == payload["request_id"]


def test_moderate_allow_path() -> None:
    response = client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "ALLOW"
    assert "R_ALLOW_NO_POLICY_MATCH" in payload["reason_codes"]
    assert payload["labels"] == ["BENIGN_POLITICAL_SPEECH"]
    assert "X-Request-ID" in response.headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


def test_moderate_uses_body_request_id_for_header() -> None:
    response = client.post(
        "/v1/moderate",
        json={"text": "This is peaceful speech", "request_id": "client-123"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "client-123"


def test_moderate_block_path() -> None:
    response = client.post(
        "/v1/moderate",
        json={"text": "They should kill them now."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "BLOCK"
    assert "INCITEMENT_VIOLENCE" in payload["labels"]
    assert "R_INCITE_CALL_TO_HARM" in payload["reason_codes"]


def test_moderate_advisory_stage_downgrades_block(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "advisory")
    response = client.post(
        "/v1/moderate",
        json={"text": "They should kill them now."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "REVIEW"
    assert payload["policy_version"].endswith("#advisory")
    assert "R_STAGE_ADVISORY_BLOCK_DOWNGRADED" in payload["reason_codes"]


def test_moderate_review_path() -> None:
    response = client.post(
        "/v1/moderate",
        json={"text": "This election is rigged."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "REVIEW"
    assert "DISINFO_RISK" in payload["labels"]
    assert "R_DISINFO_NARRATIVE_SIMILARITY" in payload["reason_codes"]


def test_moderate_code_switched_input_returns_multi_language_spans() -> None:
    response = client.post(
        "/v1/moderate",
        json={"text": "manze we should discuss sasa peacefully."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    langs = [item["lang"] for item in payload["language_spans"]]
    assert "sh" in langs
    assert "sw" in langs
    assert "en" in langs
    assert len(payload["language_spans"]) >= 3


def test_rate_limit_exceeded() -> None:
    original = rate_limiter.per_minute
    rate_limiter.per_minute = 1
    try:
        first = client.post(
            "/v1/moderate",
            json={"text": "We should discuss policy peacefully."},
            headers={"X-API-Key": TEST_API_KEY},
        )
        second = client.post(
            "/v1/moderate",
            json={"text": "We should discuss policy peacefully."},
            headers={"X-API-Key": TEST_API_KEY},
        )
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.headers["X-RateLimit-Limit"] == "1"
        assert second.headers["X-RateLimit-Remaining"] == "0"
        assert "X-RateLimit-Reset" in second.headers
        assert "Retry-After" in second.headers
        payload = second.json()
        assert payload["error_code"] == "HTTP_429"
    finally:
        rate_limiter.per_minute = original


def test_moderate_internal_error_returns_structured_500(monkeypatch) -> None:
    def broken(_text: str, *, runtime=None):
        del runtime
        raise RuntimeError("boom")

    monkeypatch.setattr("sentinel_api.main.moderate", broken)
    crash_client = TestClient(app, raise_server_exceptions=False)
    response = crash_client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 500
    payload = response.json()
    assert payload["error_code"] == "HTTP_500"
    assert payload["message"] == "Internal server error"
    assert response.headers["X-Request-ID"] == payload["request_id"]
