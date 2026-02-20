from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from sentinel_api.main import app, rate_limiter
from sentinel_api.metrics import metrics
from sentinel_api.model_registry import ClassifierShadowResult

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


def test_moderate_rejects_invalid_body_request_id() -> None:
    response = client.post(
        "/v1/moderate",
        json={"text": "This is peaceful speech", "request_id": "bad id"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "HTTP_400"


def test_middleware_ignores_invalid_header_request_id() -> None:
    response = client.get("/health", headers={"X-Request-ID": "bad id"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "bad id"


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


def test_batch_happy_path_two_items() -> None:
    response = client.post(
        "/v1/moderate/batch",
        json={
            "items": [
                {"text": "We should discuss policy peacefully."},
                {"text": "This election is rigged."},
            ]
        },
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["succeeded"] == 2
    assert payload["failed"] == 0
    assert len(payload["items"]) == 2
    assert payload["items"][0]["result"] is not None


def test_batch_partial_failure(monkeypatch) -> None:
    import sentinel_api.policy as policy

    def flaky(text: str, *, context=None, runtime=None):
        if text == "boom":
            raise RuntimeError("boom")
        return policy.moderate(text, context=context, runtime=runtime)

    monkeypatch.setattr("sentinel_api.main.moderate", flaky)

    response = client.post(
        "/v1/moderate/batch",
        json={"items": [{"text": "boom"}, {"text": "We should discuss policy peacefully."}]},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["succeeded"] == 1
    assert payload["failed"] == 1
    assert payload["items"][0]["result"] is None
    assert payload["items"][0]["error"]["error_code"] == "HTTP_500"


def test_batch_oversized_returns_validation_error() -> None:
    response = client.post(
        "/v1/moderate/batch",
        json={"items": [{"text": "hello"} for _ in range(51)]},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 400


def test_batch_rate_limit_429(monkeypatch) -> None:
    original = rate_limiter.per_minute
    rate_limiter.per_minute = 1
    try:
        monkeypatch.setattr(
            "sentinel_api.main.moderate",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
        )
        response = client.post(
            "/v1/moderate/batch",
            json={"items": [{"text": "a"}, {"text": "b"}]},
            headers={"X-API-Key": TEST_API_KEY},
        )
        assert response.status_code == 429
        assert response.headers["X-RateLimit-Limit"] == "1"
    finally:
        rate_limiter.per_minute = original


def test_batch_unauthenticated_401() -> None:
    response = client.post(
        "/v1/moderate/batch",
        json={"items": [{"text": "hello"}]},
    )
    assert response.status_code == 401


def test_moderate_uses_embedding_provider_via_env(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_EMBEDDING_PROVIDER", "e5-multilingual-small-v1")

    captured: dict[str, object] = {}

    class _Runtime:
        embedding_provider_id = "e5-multilingual-small-v1"

        class _Provider:
            def embed(self, _text: str, *, timeout_ms: int):  # type: ignore[no-untyped-def]
                del timeout_ms
                return [0.0] * 384

        embedding_provider = _Provider()

    def _fake_find_vector_match(
        _text: str,
        *,
        lexicon_version: str,
        query_embedding: list[float],
        embedding_model: str,
        min_similarity=None,
    ):
        del lexicon_version, min_similarity
        captured["embedding_model"] = embedding_model
        captured["embedding_dim"] = len(query_embedding)
        return None

    monkeypatch.setattr("sentinel_api.policy._vector_matching_configured", lambda: True)
    monkeypatch.setattr("sentinel_api.policy.get_model_runtime", lambda: _Runtime())
    monkeypatch.setattr("sentinel_api.policy.find_vector_match", _fake_find_vector_match)

    response = client.post(
        "/v1/moderate",
        json={"text": "peaceful civic dialogue"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    assert captured["embedding_model"] == "e5-multilingual-small-v1"
    assert captured["embedding_dim"] == 384


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


def test_classifier_shadow_disabled_by_default(monkeypatch) -> None:
    def _unexpected_shadow_call(text: str):
        raise AssertionError(f"shadow classifier should be disabled, text={text}")

    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "shadow")
    monkeypatch.delenv("SENTINEL_CLASSIFIER_SHADOW_ENABLED", raising=False)
    monkeypatch.setattr(
        "sentinel_api.main.predict_classifier_shadow",
        _unexpected_shadow_call,
    )

    response = client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200


def test_classifier_shadow_records_metrics_and_persistence(monkeypatch, tmp_path) -> None:
    shadow_path = tmp_path / "shadow_predictions.jsonl"
    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "advisory")
    monkeypatch.setenv("SENTINEL_CLASSIFIER_SHADOW_ENABLED", "true")
    monkeypatch.setenv("SENTINEL_SHADOW_PREDICTIONS_PATH", str(shadow_path))

    monkeypatch.setattr(
        "sentinel_api.main.predict_classifier_shadow",
        lambda _text: ClassifierShadowResult(
            provider_id="mock-provider-v1",
            model_version="mock-classifier-v1",
            predicted_labels=[("INCITEMENT_VIOLENCE", 0.99)],
            latency_ms=12,
            status="ok",
        ),
    )
    response = client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully.", "request_id": "shadow-req-1"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "ALLOW"

    shadow_metrics = metrics.classifier_shadow_snapshot()
    status_counts = shadow_metrics["status_counts"]
    assert isinstance(status_counts, dict)
    assert status_counts.get("mock-provider-v1:ok") == 1
    assert shadow_metrics["disagreement_count"] == 1

    rows = shadow_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    event = json.loads(rows[0])
    assert event["request_id"] == "shadow-req-1"
    assert event["classifier_model_version"] == "mock-classifier-v1"
    assert event["enforced_action"] == "ALLOW"
    assert event["predicted_action"] == "REVIEW"
    assert event["disagreement"] is True
