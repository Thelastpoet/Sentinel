from __future__ import annotations

import logging
import sys
import types

import sentinel_api.model_registry as model_registry


def setup_function() -> None:
    model_registry.reset_model_runtime_cache()
    model_registry.reset_classifier_shadow_state()


def teardown_function() -> None:
    model_registry.reset_model_runtime_cache()
    model_registry.reset_classifier_shadow_state()


def test_get_model_runtime_uses_default_providers() -> None:
    runtime = model_registry.get_model_runtime()
    assert runtime.embedding_provider_id == model_registry.DEFAULT_EMBEDDING_PROVIDER_ID
    assert runtime.classifier_id == model_registry.DEFAULT_CLASSIFIER_PROVIDER_ID
    assert runtime.claim_scorer_id == model_registry.DEFAULT_CLAIM_SCORER_PROVIDER_ID


def test_invalid_provider_id_falls_back_to_default(monkeypatch, caplog) -> None:
    monkeypatch.setenv(model_registry.CLAIM_SCORER_PROVIDER_ENV, "unknown-provider")
    model_registry.reset_model_runtime_cache()

    with caplog.at_level(logging.WARNING):
        runtime = model_registry.get_model_runtime()
    assert runtime.claim_scorer_id == model_registry.DEFAULT_CLAIM_SCORER_PROVIDER_ID
    assert "invalid provider configured" in caplog.text


def test_score_claim_falls_back_to_baseline_provider(monkeypatch) -> None:
    class _UnavailableClaimScorer:
        name = "unavailable"
        version = "unavailable-v1"

        def score(self, text: str, *, timeout_ms: int):
            _ = text, timeout_ms
            return None

    monkeypatch.setitem(model_registry.CLAIM_SCORERS, "unavailable-v1", _UnavailableClaimScorer())
    monkeypatch.setenv(model_registry.CLAIM_SCORER_PROVIDER_ENV, "unavailable-v1")
    model_registry.reset_model_runtime_cache()

    score = model_registry.score_claim_with_fallback(
        "IEBC results were manipulated and falsified in 12 constituencies."
    )
    assert score is not None
    assert score[0] > 0.0


def test_embedding_provider_returns_none_on_internal_error(monkeypatch, caplog) -> None:
    def _raise_embed_text(_text: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(model_registry, "embed_text", _raise_embed_text)
    provider = model_registry.HashBowEmbeddingProvider()
    with caplog.at_level(logging.WARNING):
        result = provider.embed("sample", timeout_ms=10)
    assert result is None
    assert "embedding provider failed" in caplog.text


def test_e5_provider_selected_via_env(monkeypatch) -> None:
    monkeypatch.setenv(model_registry.EMBEDDING_PROVIDER_ENV, "e5-multilingual-small-v1")
    model_registry.reset_model_runtime_cache()
    runtime = model_registry.get_model_runtime()
    assert runtime.embedding_provider_id == "e5-multilingual-small-v1"


def test_e5_embed_returns_384_floats(monkeypatch) -> None:
    class _FakeArray(list):
        def tolist(self):  # type: ignore[override]
            return list(self)

    class _FakeModel:
        def encode(self, text: str, *, normalize_embeddings: bool):
            assert normalize_embeddings is True
            assert text.startswith("query: ")
            return _FakeArray([0.0] * 384)

    class _FakeSentenceTransformer:
        def __init__(self, name: str) -> None:
            assert name == "intfloat/multilingual-e5-small"

        def encode(self, text: str, *, normalize_embeddings: bool):
            return _FakeModel().encode(text, normalize_embeddings=normalize_embeddings)

    fake_module = types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    model_registry.E5MultilingualSmallEmbeddingProvider._load_model.cache_clear()

    monkeypatch.setenv(model_registry.EMBEDDING_PROVIDER_ENV, "e5-multilingual-small-v1")
    model_registry.reset_model_runtime_cache()
    runtime = model_registry.get_model_runtime()
    provider = runtime.embedding_provider
    embedding = provider.embed("test", timeout_ms=50)
    assert embedding is not None
    assert len(embedding) == 384


def test_e5_graceful_when_sentence_transformers_missing(monkeypatch, caplog) -> None:
    monkeypatch.setenv(model_registry.EMBEDDING_PROVIDER_ENV, "e5-multilingual-small-v1")
    model_registry.reset_model_runtime_cache()
    model_registry.E5MultilingualSmallEmbeddingProvider._load_model.cache_clear()
    monkeypatch.delitem(sys.modules, "sentence_transformers", raising=False)

    provider = model_registry.E5MultilingualSmallEmbeddingProvider()
    with caplog.at_level(logging.WARNING):
        result = provider.embed("sample", timeout_ms=10)
    assert result is None
    assert "sentence-transformers not installed" in caplog.text


def test_predict_classifier_shadow_drops_unknown_and_low_scores(monkeypatch) -> None:
    class _Classifier:
        name = "test"
        version = "test-v1"
        labels = ("INCITEMENT_VIOLENCE", "DISINFO_RISK")

        def predict(self, text: str, *, timeout_ms: int):
            _ = text, timeout_ms
            return [
                ("UNKNOWN_LABEL", 0.99),
                ("DISINFO_RISK", 0.70),
                ("INCITEMENT_VIOLENCE", 0.20),
            ]

    monkeypatch.setitem(model_registry.CLASSIFIERS, "test-classifier-v1", _Classifier())
    monkeypatch.setenv(model_registry.CLASSIFIER_PROVIDER_ENV, "test-classifier-v1")
    monkeypatch.setenv(model_registry.CLASSIFIER_MIN_SCORE_ENV, "0.50")
    model_registry.reset_model_runtime_cache()

    result = model_registry.predict_classifier_shadow("Election tallies were manipulated.")
    assert result.status == "ok"
    assert result.model_version == "test-v1"
    assert result.predicted_labels == [("DISINFO_RISK", 0.70)]


def test_predict_classifier_shadow_opens_circuit_on_repeated_failure(monkeypatch) -> None:
    class _FailingClassifier:
        name = "failing"
        version = "failing-v1"
        labels = ("DISINFO_RISK",)

        def predict(self, text: str, *, timeout_ms: int):
            _ = text, timeout_ms
            raise RuntimeError("provider failure")

    monkeypatch.setitem(model_registry.CLASSIFIERS, "failing-v1", _FailingClassifier())
    monkeypatch.setenv(model_registry.CLASSIFIER_PROVIDER_ENV, "failing-v1")
    monkeypatch.setenv(model_registry.CLASSIFIER_CIRCUIT_FAILURE_THRESHOLD_ENV, "2")
    monkeypatch.setenv(model_registry.CLASSIFIER_CIRCUIT_RESET_SECONDS_ENV, "120")
    model_registry.reset_model_runtime_cache()
    model_registry.reset_classifier_shadow_state()

    first = model_registry.predict_classifier_shadow("test text")
    second = model_registry.predict_classifier_shadow("test text")
    third = model_registry.predict_classifier_shadow("test text")

    assert first.status == "error"
    assert second.status == "error"
    assert third.status == "circuit_open"
