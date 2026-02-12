from __future__ import annotations

import os

import pytest

from sentinel_api.lexicon import get_lexicon_matcher, reset_lexicon_cache
from sentinel_api.policy import moderate


def _integration_db_url() -> str | None:
    return os.getenv("SENTINEL_INTEGRATION_DB_URL")


def setup_function() -> None:
    reset_lexicon_cache()


def teardown_function() -> None:
    reset_lexicon_cache()


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_db_backed_lexicon_loader(monkeypatch) -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    monkeypatch.setenv("SENTINEL_DATABASE_URL", db_url)
    monkeypatch.setenv("SENTINEL_LEXICON_PATH", "/tmp/sentinel-no-fallback.json")
    matcher = get_lexicon_matcher()
    assert matcher.version == "hatelex-v2.1"
    assert any(entry.term == "kill" for entry in matcher.entries)


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_policy_uses_db_lexicon(monkeypatch) -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    monkeypatch.setenv("SENTINEL_DATABASE_URL", db_url)
    monkeypatch.setenv("SENTINEL_LEXICON_PATH", "/tmp/sentinel-no-fallback.json")
    response = moderate("They should kill them now.")
    assert response.action == "BLOCK"
    assert "R_INCITE_CALL_TO_HARM" in response.reason_codes
    assert response.lexicon_version == "hatelex-v2.1"
