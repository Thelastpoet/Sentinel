from __future__ import annotations

import pytest
from fastapi import HTTPException

from sentinel_api.main import require_api_key
from sentinel_api.oauth import authenticate_bearer_token


def test_require_api_key_fails_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTINEL_API_KEY", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        require_api_key("any-value")
    assert exc_info.value.status_code == 503


def test_require_api_key_rejects_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_API_KEY", "expected-api-key")
    with pytest.raises(HTTPException) as exc_info:
        require_api_key("wrong-key")
    assert exc_info.value.status_code == 401


def test_authenticate_bearer_token_rejects_when_registry_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SENTINEL_OAUTH_TOKENS_JSON", raising=False)
    monkeypatch.delenv("SENTINEL_OAUTH_JWT_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        authenticate_bearer_token("Bearer internal-dev-token")
    assert exc_info.value.status_code == 401
