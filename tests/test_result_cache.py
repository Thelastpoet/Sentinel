from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import sentinel_api.main as main
from sentinel_api.result_cache import make_cache_key
from sentinel_core.models import ModerationContext, ModerationResponse

client = TestClient(main.app)


def test_cache_key_includes_all_provenance_fields() -> None:
    base = make_cache_key(
        "hello",
        policy_version="p1",
        lexicon_version="l1",
        model_version="m1",
        pack_versions={"en": "pack-en-0.1"},
        deployment_stage="supervised",
        context=None,
    )
    different_policy = make_cache_key(
        "hello",
        policy_version="p2",
        lexicon_version="l1",
        model_version="m1",
        pack_versions={"en": "pack-en-0.1"},
        deployment_stage="supervised",
        context=None,
    )
    assert base != different_policy


def test_different_context_produces_different_key() -> None:
    none_key = make_cache_key(
        "hello",
        policy_version="p1",
        lexicon_version="l1",
        model_version="m1",
        pack_versions={"en": "pack-en-0.1"},
        deployment_stage="supervised",
        context=None,
    )
    forward_key = make_cache_key(
        "hello",
        policy_version="p1",
        lexicon_version="l1",
        model_version="m1",
        pack_versions={"en": "pack-en-0.1"},
        deployment_stage="supervised",
        context=ModerationContext(channel="forward"),
    )
    assert none_key != forward_key


def test_cache_disabled_no_redis_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTINEL_RESULT_CACHE_ENABLED", raising=False)
    monkeypatch.setenv("SENTINEL_API_KEY", "k")
    monkeypatch.setattr(
        main,
        "get_cached_result",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call redis")),
    )
    response = client.post(
        "/v1/moderate", json={"text": "peaceful debate"}, headers={"X-API-Key": "k"}
    )
    assert response.status_code == 200
    assert "X-Cache" not in response.headers


def test_cache_hit_returns_cached_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_RESULT_CACHE_ENABLED", "true")
    monkeypatch.setenv("SENTINEL_REDIS_URL", "redis://unused")
    monkeypatch.setenv("SENTINEL_API_KEY", "k")

    cached = ModerationResponse.model_validate(
        {
            "toxicity": 0.0,
            "labels": ["BENIGN_POLITICAL_SPEECH"],
            "action": "ALLOW",
            "reason_codes": ["R_ALLOW_NO_POLICY_MATCH"],
            "evidence": [{"type": "model_span", "span": "x", "confidence": 0.9}],
            "language_spans": [{"start": 0, "end": 1, "lang": "en"}],
            "model_version": "sentinel-multi-v2",
            "lexicon_version": "hatelex-v2.1",
            "pack_versions": {"en": "pack-en-0.1"},
            "policy_version": "policy-2026.01",
            "latency_ms": 1,
        }
    )

    monkeypatch.setattr(main, "get_cached_result", lambda *_args, **_kwargs: cached)
    monkeypatch.setattr(
        main,
        "set_cached_result",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not write on hit")),
    )

    response = client.post("/v1/moderate", json={"text": "hello"}, headers={"X-API-Key": "k"})
    assert response.status_code == 200
    assert response.headers["X-Cache"] == "HIT"
    assert response.json()["policy_version"] == "policy-2026.01"


def test_cache_miss_sets_cached_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_RESULT_CACHE_ENABLED", "true")
    monkeypatch.setenv("SENTINEL_REDIS_URL", "redis://unused")
    monkeypatch.setenv("SENTINEL_API_KEY", "k")
    monkeypatch.setattr(main, "get_cached_result", lambda *_args, **_kwargs: None)
    captured: dict[str, object] = {}

    def _capture_set(
        cache_key: str, result: ModerationResponse, redis_url: str, *, ttl: int
    ) -> None:
        captured["cache_key"] = cache_key
        captured["redis_url"] = redis_url
        captured["ttl"] = ttl
        captured["action"] = result.action

    monkeypatch.setattr(main, "set_cached_result", _capture_set)

    response = client.post(
        "/v1/moderate",
        json={"text": "We should discuss policy peacefully."},
        headers={"X-API-Key": "k"},
    )
    assert response.status_code == 200
    assert response.headers["X-Cache"] == "MISS"
    assert captured["redis_url"] == "redis://unused"
    assert captured["ttl"] == 60
    assert captured["action"] in {"ALLOW", "REVIEW", "BLOCK"}
