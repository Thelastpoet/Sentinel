from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel_api.main import app, rate_limiter
from sentinel_api.metrics import metrics
from sentinel_api.model_registry import ClassifierShadowResult

client = TestClient(app)
TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def reset_runtime_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_API_KEY", TEST_API_KEY)
    rate_limiter.reset()
    metrics.reset()


def test_metrics_endpoint_exposes_counters() -> None:
    health = client.get("/health")
    assert health.status_code == 200

    moderate = client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert moderate.status_code == 200

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    payload = metrics_response.json()
    assert payload["action_counts"]["ALLOW"] == 1
    assert int(payload["http_status_counts"]["200"]) >= 2
    assert sum(payload["latency_ms_buckets"].values()) == 1
    assert payload["validation_error_count"] == 0


def test_metrics_tracks_validation_errors() -> None:
    invalid = client.post("/v1/moderate", json={}, headers={"X-API-Key": TEST_API_KEY})
    assert invalid.status_code == 400

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    payload = metrics_response.json()
    assert payload["validation_error_count"] == 1
    assert int(payload["http_status_counts"]["400"]) >= 1


def test_metrics_latency_bucket_counter_increments_only_for_moderation() -> None:
    health = client.get("/health")
    assert health.status_code == 200

    before = client.get("/metrics")
    assert before.status_code == 200
    assert sum(before.json()["latency_ms_buckets"].values()) == 0

    moderate = client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert moderate.status_code == 200

    after = client.get("/metrics")
    assert after.status_code == 200
    assert sum(after.json()["latency_ms_buckets"].values()) == 1


def test_prometheus_metrics_endpoint_exposes_counters() -> None:
    moderate = client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert moderate.status_code == 200

    response = client.get("/metrics/prometheus")
    assert response.status_code == 200
    assert "sentinel_action_total" in response.text
    assert "sentinel_http_status_total" in response.text


def test_prometheus_metrics_include_classifier_shadow_observability(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_CLASSIFIER_SHADOW_ENABLED", "true")
    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "advisory")
    monkeypatch.setattr(
        "sentinel_api.main.predict_classifier_shadow",
        lambda _text: ClassifierShadowResult(
            provider_id="mock-provider-v1",
            model_version="mock-classifier-v1",
            predicted_labels=[("DISINFO_RISK", 0.86)],
            latency_ms=11,
            status="ok",
        ),
    )
    moderate = client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully."},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert moderate.status_code == 200

    response = client.get("/metrics/prometheus")
    assert response.status_code == 200
    assert "sentinel_classifier_shadow_total" in response.text
    assert "sentinel_classifier_shadow_latency_ms" in response.text
    assert "sentinel_classifier_shadow_disagreement_total" in response.text
