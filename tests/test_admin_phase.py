from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from sentinel_api.main import app
from sentinel_core.policy_config import (
    ElectoralPhase,
    get_policy_config,
    resolve_policy_runtime,
    set_runtime_phase_override,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_runtime_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SENTINEL_ELECTORAL_PHASE", raising=False)
    monkeypatch.delenv("SENTINEL_OAUTH_TOKENS_JSON", raising=False)
    set_runtime_phase_override(None)
    yield
    set_runtime_phase_override(None)


def _set_registry(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]) -> None:
    monkeypatch.setenv("SENTINEL_OAUTH_TOKENS_JSON", json.dumps(payload))


def test_runtime_override_takes_priority_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_ELECTORAL_PHASE", "campaign")
    set_runtime_phase_override(ElectoralPhase.VOTING_DAY)
    runtime = resolve_policy_runtime()
    assert runtime.effective_phase == ElectoralPhase.VOTING_DAY


def test_clearing_override_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_ELECTORAL_PHASE", "campaign")
    set_runtime_phase_override(ElectoralPhase.VOTING_DAY)
    set_runtime_phase_override(None)
    runtime = resolve_policy_runtime()
    assert runtime.effective_phase == ElectoralPhase.CAMPAIGN


def test_runtime_uses_config_when_no_env_and_no_override() -> None:
    config = get_policy_config()
    runtime = resolve_policy_runtime()
    assert runtime.effective_phase == config.electoral_phase


def test_admin_phase_endpoint_requires_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-admin-read-only": {
                "client_id": "admin-reader",
                "scopes": ["admin:proposal:read"],
            }
        },
    )
    response = client.post(
        "/admin/policy/phase",
        headers={"Authorization": "Bearer token-admin-read-only"},
        json={"phase": "voting_day"},
    )
    assert response.status_code == 403


def test_admin_phase_endpoint_sets_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_registry(
        monkeypatch,
        {
            "token-admin-writer": {
                "client_id": "admin-writer",
                "scopes": ["admin:policy:write"],
            }
        },
    )
    response = client.post(
        "/admin/policy/phase",
        headers={"Authorization": "Bearer token-admin-writer"},
        json={"phase": "voting_day"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_phase"] == "voting_day"
