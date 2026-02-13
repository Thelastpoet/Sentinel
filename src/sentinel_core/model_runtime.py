from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

ClaimBand = Literal["low", "medium", "high"]


class EmbeddingProvider(Protocol):
    name: str
    version: str
    dimension: int

    def embed(self, text: str, *, timeout_ms: int) -> list[float] | None: ...


class MultiLabelClassifier(Protocol):
    name: str
    version: str
    labels: tuple[str, ...]

    def predict(self, text: str, *, timeout_ms: int) -> list[tuple[str, float]] | None: ...


class ClaimScorer(Protocol):
    name: str
    version: str

    def score(self, text: str, *, timeout_ms: int) -> tuple[float, ClaimBand] | None: ...


@dataclass(frozen=True)
class ModelRuntimeProviders:
    embedding_provider_id: str
    embedding_provider: EmbeddingProvider
    classifier_id: str
    classifier: MultiLabelClassifier
    claim_scorer_id: str
    claim_scorer: ClaimScorer
