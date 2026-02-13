from __future__ import annotations

from sentinel_api import model_artifact_repository as mar


def setup_function() -> None:
    mar.reset_model_artifact_cache()


def teardown_function() -> None:
    mar.reset_model_artifact_cache()


def test_resolve_runtime_model_version_returns_default_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("SENTINEL_DATABASE_URL", raising=False)
    assert mar.resolve_runtime_model_version("sentinel-multi-v2") == "sentinel-multi-v2"


def test_resolve_runtime_model_version_uses_active_artifact_with_cache(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_fetch(database_url: str) -> str | None:
        calls.append(database_url)
        return "model-governed-v2"

    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example/sentinel")
    monkeypatch.setattr(mar, "_fetch_active_model_id", _fake_fetch)

    first = mar.resolve_runtime_model_version("sentinel-multi-v2")
    second = mar.resolve_runtime_model_version("sentinel-multi-v2")

    assert first == "model-governed-v2"
    assert second == "model-governed-v2"
    assert calls == ["postgresql://example/sentinel"]


def test_resolve_runtime_model_version_falls_back_when_lookup_errors(monkeypatch) -> None:
    calls = 0

    def _fake_fetch(_database_url: str) -> str | None:
        nonlocal calls
        calls += 1
        raise RuntimeError("db unavailable")

    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example/sentinel")
    monkeypatch.setattr(mar, "_fetch_active_model_id", _fake_fetch)

    assert mar.resolve_runtime_model_version("sentinel-multi-v2") == "sentinel-multi-v2"
    assert mar.resolve_runtime_model_version("sentinel-multi-v2") == "sentinel-multi-v2"
    assert calls == 1


def test_reset_model_artifact_cache_forces_refresh(monkeypatch) -> None:
    calls = 0

    def _fake_fetch(_database_url: str) -> str | None:
        nonlocal calls
        calls += 1
        return "model-governed-v2"

    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example/sentinel")
    monkeypatch.setattr(mar, "_fetch_active_model_id", _fake_fetch)

    assert mar.resolve_runtime_model_version("sentinel-multi-v2") == "model-governed-v2"
    mar.reset_model_artifact_cache()
    assert mar.resolve_runtime_model_version("sentinel-multi-v2") == "model-governed-v2"
    assert calls == 2
