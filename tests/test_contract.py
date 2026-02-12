from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sentinel_api.main import app

client = TestClient(app)
TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_API_KEY", TEST_API_KEY)


def test_response_contains_all_required_schema_fields() -> None:
    schema_path = Path("docs/specs/schemas/moderation-response.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema["required"])

    response = client.post(
        "/v1/moderate",
        json={"text": "msee this is a peaceful conversation"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    assert required.issubset(set(payload.keys()))


def test_request_schema_text_required() -> None:
    response = client.post("/v1/moderate", json={}, headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "HTTP_400"
    assert "message" in payload


def test_metrics_response_contains_required_schema_fields() -> None:
    schema_path = Path("docs/specs/schemas/metrics-response.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema["required"])

    response = client.get("/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert required.issubset(set(payload.keys()))


def test_internal_async_schema_files_exist_and_are_object_contracts() -> None:
    schema_paths = [
        Path("docs/specs/schemas/internal/monitoring-queue-item.schema.json"),
        Path("docs/specs/schemas/internal/monitoring-cluster.schema.json"),
        Path("docs/specs/schemas/internal/release-proposal.schema.json"),
        Path("docs/specs/schemas/internal/proposal-review-event.schema.json"),
    ]
    for schema_path in schema_paths:
        assert schema_path.exists(), f"missing schema: {schema_path}"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert len(schema.get("required", [])) > 0
