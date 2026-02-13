from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import cast, get_args

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

DEFAULT_EMBEDDING_PROVIDER_ID = "hash-bow-v1"
DEFAULT_CLASSIFIER_PROVIDER_ID = "none-v1"
DEFAULT_CLAIM_SCORER_PROVIDER_ID = "claim-heuristic-v1"

DEFAULT_MODEL_TIMEOUT_MS = 40


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


class NoopMultiLabelClassifier:
    name = "none"
    version = "none-v1"
    labels = cast(tuple[str, ...], tuple(get_args(Label)))

    def predict(self, text: str, *, timeout_ms: int) -> list[tuple[str, float]] | None:
        _ = text, timeout_ms
        return None


class HeuristicClaimScorer:
    name = "claim-heuristic"
    version = "claim-heuristic-v1"

    def score(self, text: str, *, timeout_ms: int) -> tuple[float, ClaimBand] | None:
        _ = timeout_ms
        try:
            assessment = assess_claim_likeness(
                text,
                medium_threshold=0.40,
                high_threshold=0.70,
            )
        except Exception as exc:
            logger.warning("claim scorer failed; falling back: %s", exc)
            return None
        return assessment.score, assessment.band


EMBEDDING_PROVIDERS: dict[str, EmbeddingProvider] = {
    DEFAULT_EMBEDDING_PROVIDER_ID: HashBowEmbeddingProvider(),
}
CLASSIFIERS: dict[str, MultiLabelClassifier] = {
    DEFAULT_CLASSIFIER_PROVIDER_ID: NoopMultiLabelClassifier(),
}
CLAIM_SCORERS: dict[str, ClaimScorer] = {
    DEFAULT_CLAIM_SCORER_PROVIDER_ID: HeuristicClaimScorer(),
}


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
