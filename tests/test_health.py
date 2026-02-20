from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel_api.main import app

client = TestClient(app)


def test_live_always_200() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_200_with_lexicon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTINEL_DATABASE_URL", raising=False)
    monkeypatch.delenv("SENTINEL_REDIS_URL", raising=False)
    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["lexicon"] in {"ok", "empty"}


def test_ready_503_when_db_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://invalid")
    monkeypatch.setattr("sentinel_api.main._check_db_ready", lambda _url: "error")
    response = client.get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["db"] == "error"


def test_ready_200_no_db_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTINEL_DATABASE_URL", raising=False)
    monkeypatch.delenv("SENTINEL_REDIS_URL", raising=False)
    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert "db" not in payload["checks"]


def test_existing_health_unchanged() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
