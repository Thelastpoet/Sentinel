from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Label = Literal[
    "ETHNIC_CONTEMPT",
    "INCITEMENT_VIOLENCE",
    "HARASSMENT_THREAT",
    "DOGWHISTLE_WATCH",
    "DISINFO_RISK",
    "BENIGN_POLITICAL_SPEECH",
]

Action = Literal["ALLOW", "REVIEW", "BLOCK"]
EvidenceType = Literal["lexicon", "vector_match", "model_span"]
ReasonCode = Annotated[str, StringConstraints(pattern=r"^R_[A-Z0-9_]+$")]


class ModerationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str | None = Field(default=None, max_length=100)
    locale: str | None = Field(default=None, max_length=20)
    channel: str | None = Field(default=None, max_length=50)


class ModerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=5000)
    context: ModerationContext | None = None
    request_id: str | None = Field(default=None, max_length=128)


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: EvidenceType
    match: str | None = None
    severity: int | None = Field(default=None, ge=1, le=3)
    lang: str | None = None
    match_id: str | None = None
    similarity: float | None = Field(default=None, ge=0, le=1)
    span: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class LanguageSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    lang: str = Field(max_length=16)


class ModerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    toxicity: float = Field(ge=0, le=1)
    labels: list[Label]
    action: Action
    reason_codes: list[ReasonCode] = Field(min_length=1)
    evidence: list[EvidenceItem]
    language_spans: list[LanguageSpan]
    model_version: str
    lexicon_version: str
    pack_versions: dict[str, str]
    policy_version: str
    latency_ms: int = Field(ge=0)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    request_id: str | None = None


class MetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_counts: dict[str, int]
    http_status_counts: dict[str, int]
    latency_ms_buckets: dict[str, int]
    validation_error_count: int = Field(ge=0)
