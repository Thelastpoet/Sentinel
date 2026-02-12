from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from sentinel_api.main import app, rate_limiter
from sentinel_api.metrics import metrics

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_runtime_state() -> None:
    rate_limiter.reset()
    metrics.reset()


def test_metrics_endpoint_exposes_counters() -> None:
    health = client.get("/health")
    assert health.status_code == 200

    moderate = client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully."},
        headers={"X-API-Key": "dev-key"},
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
    invalid = client.post("/v1/moderate", json={}, headers={"X-API-Key": "dev-key"})
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
        headers={"X-API-Key": "dev-key"},
    )
    assert moderate.status_code == 200

    after = client.get("/metrics")
    assert after.status_code == 200
    assert sum(after.json()["latency_ms_buckets"].values()) == 1
