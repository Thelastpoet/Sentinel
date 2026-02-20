from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from threading import Lock
from typing import Literal, cast, get_args

from sentinel_core.claim_likeness import assess_claim_likeness
from sentinel_core.model_runtime import (
    ClaimBand,
    ClaimScorer,
    EmbeddingProvider,
    ModelRuntimeProviders,
    MultiLabelClassifier,
)
from sentinel_core.models import Label
from sentinel_lexicon.vector_matcher import VECTOR_DIMENSION, VECTOR_MODEL, embed_text

logger = logging.getLogger(__name__)

EMBEDDING_PROVIDER_ENV = "SENTINEL_EMBEDDING_PROVIDER"
CLASSIFIER_PROVIDER_ENV = "SENTINEL_CLASSIFIER_PROVIDER"
CLAIM_SCORER_PROVIDER_ENV = "SENTINEL_CLAIM_SCORER_PROVIDER"
CLASSIFIER_TIMEOUT_MS_ENV = "SENTINEL_CLASSIFIER_TIMEOUT_MS"
CLASSIFIER_MIN_SCORE_ENV = "SENTINEL_CLASSIFIER_MIN_SCORE"
CLASSIFIER_CIRCUIT_FAILURE_THRESHOLD_ENV = "SENTINEL_CLASSIFIER_CIRCUIT_FAILURE_THRESHOLD"
CLASSIFIER_CIRCUIT_RESET_SECONDS_ENV = "SENTINEL_CLASSIFIER_CIRCUIT_RESET_SECONDS"

DEFAULT_EMBEDDING_PROVIDER_ID = "hash-bow-v1"
DEFAULT_CLASSIFIER_PROVIDER_ID = "none-v1"
KEYWORD_CLASSIFIER_PROVIDER_ID = "keyword-shadow-v1"
DEFAULT_CLAIM_SCORER_PROVIDER_ID = "claim-heuristic-v1"

DEFAULT_MODEL_TIMEOUT_MS = 40
DEFAULT_CLASSIFIER_MIN_SCORE = 0.55
DEFAULT_CLASSIFIER_CIRCUIT_FAILURE_THRESHOLD = 3
DEFAULT_CLASSIFIER_CIRCUIT_RESET_SECONDS = 120
KNOWN_LABELS = set(get_args(Label))

ClassifierShadowStatus = Literal["ok", "timeout", "error", "circuit_open"]


@dataclass(frozen=True)
class ClassifierShadowResult:
    provider_id: str
    model_version: str
    predicted_labels: list[tuple[Label, float]]
    latency_ms: int
    status: ClassifierShadowStatus


class HashBowEmbeddingProvider:
    name = "hash-bow"
    version = VECTOR_MODEL
    dimension = VECTOR_DIMENSION

    def embed(self, text: str, *, timeout_ms: int) -> list[float] | None:
        _ = timeout_ms
        try:
            return embed_text(text)
        except Exception as exc:
            logger.warning("embedding provider failed; falling back: %s", exc)
            return None


class E5MultilingualSmallEmbeddingProvider:
    name = "e5-multilingual-small"
    version = "e5-multilingual-small-v1"
    dimension = 384

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_model():
        try:
            from sentence_transformers import SentenceTransformer

            return SentenceTransformer("intfloat/multilingual-e5-small")
        except ImportError:
            logger.warning("sentence-transformers not installed; e5 provider unavailable")
            return None
        except Exception as exc:
            logger.warning("failed to load e5 model: %s", exc)
            return None

    def embed(self, text: str, *, timeout_ms: int) -> list[float] | None:
        _ = timeout_ms
        model = self._load_model()
        if model is None:
            return None
        try:
            embedding = model.encode(f"query: {text}", normalize_embeddings=True)
            if hasattr(embedding, "tolist"):
                return embedding.tolist()
            return list(embedding)
        except Exception as exc:
            logger.warning("e5 embedding provider failed; falling back: %s", exc)
            return None

    def embed_passage(self, text: str, *, timeout_ms: int) -> list[float] | None:
        _ = timeout_ms
        model = self._load_model()
        if model is None:
            return None
        try:
            embedding = model.encode(f"passage: {text}", normalize_embeddings=True)
            if hasattr(embedding, "tolist"):
                return embedding.tolist()
            return list(embedding)
        except Exception as exc:
            logger.warning("e5 passage embedding failed; falling back: %s", exc)
            return None


class NoopMultiLabelClassifier:
    name = "none"
    version = "none-v1"
    labels = cast(tuple[str, ...], tuple(get_args(Label)))

    def predict(self, text: str, *, timeout_ms: int) -> list[tuple[str, float]] | None:
        _ = text, timeout_ms
        return None


class KeywordShadowMultiLabelClassifier:
    name = "keyword-shadow"
    version = "keyword-shadow-v1"
    labels = cast(tuple[str, ...], tuple(get_args(Label)))

    _KEYWORDS: dict[Label, tuple[str, ...]] = {
        "ETHNIC_CONTEMPT": ("madoadoa", "mchome", "kabila", "tribe", "cockroach"),
        "INCITEMENT_VIOLENCE": ("kill", "burn", "attack", "slaughter", "eliminate"),
        "HARASSMENT_THREAT": ("threat", "rape", "beat", "lynch", "hunt"),
        "DOGWHISTLE_WATCH": ("traitor", "outsider", "cleanse", "purge", "enemy"),
        "DISINFO_RISK": ("rigged", "stolen", "fraud", "manipulated", "falsified"),
        "BENIGN_POLITICAL_SPEECH": ("policy", "debate", "governance", "peacefully"),
    }

    def predict(self, text: str, *, timeout_ms: int) -> list[tuple[str, float]] | None:
        _ = timeout_ms
        tokens = set(re.findall(r"[a-z0-9']+", text.lower()))
        if not tokens:
            return []
        predictions: list[tuple[str, float]] = []
        for label, keywords in self._KEYWORDS.items():
            matches = sum(1 for keyword in keywords if keyword in tokens)
            if matches == 0:
                continue
            score = min(0.99, 0.35 + (0.2 * matches))
            predictions.append((label, score))
        predictions.sort(key=lambda item: item[1], reverse=True)
        return predictions


class HeuristicClaimScorer:
    name = "claim-heuristic"
    version = "claim-heuristic-v1"

    def score(self, text: str, *, timeout_ms: int) -> tuple[float, ClaimBand] | None:
        _ = timeout_ms
        try:
            assessment = assess_claim_likeness(
                text,
                medium_threshold=0.45,
                high_threshold=0.75,
            )
        except Exception as exc:
            logger.warning("claim scorer failed; falling back: %s", exc)
            return None
        return assessment.score, assessment.band


EMBEDDING_PROVIDERS: dict[str, EmbeddingProvider] = {
    DEFAULT_EMBEDDING_PROVIDER_ID: HashBowEmbeddingProvider(),
    "e5-multilingual-small-v1": E5MultilingualSmallEmbeddingProvider(),
}
CLASSIFIERS: dict[str, MultiLabelClassifier] = {
    DEFAULT_CLASSIFIER_PROVIDER_ID: NoopMultiLabelClassifier(),
    KEYWORD_CLASSIFIER_PROVIDER_ID: KeywordShadowMultiLabelClassifier(),
}
CLAIM_SCORERS: dict[str, ClaimScorer] = {
    DEFAULT_CLAIM_SCORER_PROVIDER_ID: HeuristicClaimScorer(),
}


@dataclass
class _ClassifierCircuitState:
    lock: Lock = field(default_factory=Lock)
    consecutive_failures: int = 0
    open_until_monotonic: float | None = None

    def reset(self) -> None:
        with self.lock:
            self.consecutive_failures = 0
            self.open_until_monotonic = None

    def is_open(self, *, now_monotonic: float) -> bool:
        with self.lock:
            if self.open_until_monotonic is None:
                return False
            if now_monotonic >= self.open_until_monotonic:
                self.consecutive_failures = 0
                self.open_until_monotonic = None
                return False
            return True

    def record_success(self) -> None:
        with self.lock:
            self.consecutive_failures = 0
            self.open_until_monotonic = None

    def record_failure(
        self,
        *,
        now_monotonic: float,
        failure_threshold: int,
        reset_seconds: int,
    ) -> None:
        with self.lock:
            self.consecutive_failures += 1
            if self.consecutive_failures >= max(1, failure_threshold):
                self.open_until_monotonic = now_monotonic + float(max(1, reset_seconds))


_CLASSIFIER_CIRCUIT_STATE = _ClassifierCircuitState()


def _read_int_env(name: str, *, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("invalid integer for %s: %s (using default=%s)", name, raw, default)
        return default
    return max(minimum, value)


def _read_float_env(name: str, *, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("invalid float for %s: %s (using default=%s)", name, raw, default)
        return default
    return min(maximum, max(minimum, value))


def _normalize_classifier_predictions(
    predictions: list[tuple[str, float]] | None,
    *,
    min_score: float,
) -> list[tuple[Label, float]]:
    if not predictions:
        return []
    best_by_label: dict[Label, float] = {}
    for label_raw, score_raw in predictions:
        if label_raw not in KNOWN_LABELS:
            continue
        if score_raw < 0 or score_raw > 1:
            continue
        if score_raw < min_score:
            continue
        label = cast(Label, label_raw)
        current = best_by_label.get(label)
        if current is None or score_raw > current:
            best_by_label[label] = score_raw
    normalized: list[tuple[Label, float]] = [
        (label, score) for label, score in best_by_label.items()
    ]
    normalized.sort(key=lambda item: item[1], reverse=True)
    return normalized


def _resolve_provider_id(
    *,
    env_var: str,
    default_id: str,
    registry_keys: set[str],
) -> str:
    selected = os.getenv(env_var, default_id).strip() or default_id
    if selected in registry_keys:
        return selected
    logger.warning(
        "invalid provider configured for %s: %s (falling back to %s)",
        env_var,
        selected,
        default_id,
    )
    return default_id


def reset_model_runtime_cache() -> None:
    get_model_runtime.cache_clear()


def reset_classifier_shadow_state() -> None:
    _CLASSIFIER_CIRCUIT_STATE.reset()


@lru_cache(maxsize=1)
def get_model_runtime() -> ModelRuntimeProviders:
    embedding_provider_id = _resolve_provider_id(
        env_var=EMBEDDING_PROVIDER_ENV,
        default_id=DEFAULT_EMBEDDING_PROVIDER_ID,
        registry_keys=set(EMBEDDING_PROVIDERS.keys()),
    )
    classifier_id = _resolve_provider_id(
        env_var=CLASSIFIER_PROVIDER_ENV,
        default_id=DEFAULT_CLASSIFIER_PROVIDER_ID,
        registry_keys=set(CLASSIFIERS.keys()),
    )
    claim_scorer_id = _resolve_provider_id(
        env_var=CLAIM_SCORER_PROVIDER_ENV,
        default_id=DEFAULT_CLAIM_SCORER_PROVIDER_ID,
        registry_keys=set(CLAIM_SCORERS.keys()),
    )
    return ModelRuntimeProviders(
        embedding_provider_id=embedding_provider_id,
        embedding_provider=EMBEDDING_PROVIDERS[embedding_provider_id],
        classifier_id=classifier_id,
        classifier=CLASSIFIERS[classifier_id],
        claim_scorer_id=claim_scorer_id,
        claim_scorer=CLAIM_SCORERS[claim_scorer_id],
    )


def score_claim_with_fallback(
    text: str,
    *,
    timeout_ms: int = DEFAULT_MODEL_TIMEOUT_MS,
) -> tuple[float, ClaimBand] | None:
    runtime = get_model_runtime()
    score = runtime.claim_scorer.score(text, timeout_ms=timeout_ms)
    if score is not None:
        return score
    if runtime.claim_scorer_id == DEFAULT_CLAIM_SCORER_PROVIDER_ID:
        return None
    baseline = CLAIM_SCORERS[DEFAULT_CLAIM_SCORER_PROVIDER_ID]
    return baseline.score(text, timeout_ms=timeout_ms)


def predict_classifier_shadow(
    text: str,
    *,
    timeout_ms: int | None = None,
    min_score: float | None = None,
) -> ClassifierShadowResult:
    runtime = get_model_runtime()
    timeout_budget_ms = (
        _read_int_env(
            CLASSIFIER_TIMEOUT_MS_ENV,
            default=DEFAULT_MODEL_TIMEOUT_MS,
            minimum=1,
        )
        if timeout_ms is None
        else max(1, timeout_ms)
    )
    min_score_threshold = (
        _read_float_env(
            CLASSIFIER_MIN_SCORE_ENV,
            default=DEFAULT_CLASSIFIER_MIN_SCORE,
            minimum=0.0,
            maximum=1.0,
        )
        if min_score is None
        else min(1.0, max(0.0, min_score))
    )
    circuit_failure_threshold = _read_int_env(
        CLASSIFIER_CIRCUIT_FAILURE_THRESHOLD_ENV,
        default=DEFAULT_CLASSIFIER_CIRCUIT_FAILURE_THRESHOLD,
        minimum=1,
    )
    circuit_reset_seconds = _read_int_env(
        CLASSIFIER_CIRCUIT_RESET_SECONDS_ENV,
        default=DEFAULT_CLASSIFIER_CIRCUIT_RESET_SECONDS,
        minimum=1,
    )

    now_monotonic = time.monotonic()
    if _CLASSIFIER_CIRCUIT_STATE.is_open(now_monotonic=now_monotonic):
        return ClassifierShadowResult(
            provider_id=runtime.classifier_id,
            model_version=runtime.classifier.version,
            predicted_labels=[],
            latency_ms=0,
            status="circuit_open",
        )

    start = time.perf_counter()
    try:
        predictions = runtime.classifier.predict(text, timeout_ms=timeout_budget_ms)
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("classifier provider failed; shadow path disabled for request: %s", exc)
        _CLASSIFIER_CIRCUIT_STATE.record_failure(
            now_monotonic=time.monotonic(),
            failure_threshold=circuit_failure_threshold,
            reset_seconds=circuit_reset_seconds,
        )
        return ClassifierShadowResult(
            provider_id=runtime.classifier_id,
            model_version=runtime.classifier.version,
            predicted_labels=[],
            latency_ms=latency_ms,
            status="error",
        )

    latency_ms = int((time.perf_counter() - start) * 1000)
    if latency_ms > timeout_budget_ms:
        logger.warning(
            "classifier provider timed out: provider=%s timeout_ms=%s latency_ms=%s",
            runtime.classifier_id,
            timeout_budget_ms,
            latency_ms,
        )
        _CLASSIFIER_CIRCUIT_STATE.record_failure(
            now_monotonic=time.monotonic(),
            failure_threshold=circuit_failure_threshold,
            reset_seconds=circuit_reset_seconds,
        )
        return ClassifierShadowResult(
            provider_id=runtime.classifier_id,
            model_version=runtime.classifier.version,
            predicted_labels=[],
            latency_ms=latency_ms,
            status="timeout",
        )

    _CLASSIFIER_CIRCUIT_STATE.record_success()
    return ClassifierShadowResult(
        provider_id=runtime.classifier_id,
        model_version=runtime.classifier.version,
        predicted_labels=_normalize_classifier_predictions(
            predictions,
            min_score=min_score_threshold,
        ),
        latency_ms=latency_ms,
        status="ok",
    )
