from __future__ import annotations

import json
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ReasonCode = Annotated[str, StringConstraints(pattern=r"^R_[A-Z0-9_]+$")]


class ToxicityByAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    BLOCK: float = Field(ge=0, le=1)
    REVIEW: float = Field(ge=0, le=1)
    ALLOW: float = Field(ge=0, le=1)


class LanguageHints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sw: list[str]
    sh: list[str]


class ElectoralPhase(str, Enum):
    PRE_CAMPAIGN = "pre_campaign"
    CAMPAIGN = "campaign"
    SILENCE_PERIOD = "silence_period"
    VOTING_DAY = "voting_day"
    RESULTS_PERIOD = "results_period"


class DeploymentStage(str, Enum):
    SHADOW = "shadow"
    ADVISORY = "advisory"
    SUPERVISED = "supervised"


class PhasePolicyOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    toxicity_by_action: ToxicityByAction | None = None
    allow_confidence: float | None = Field(default=None, ge=0, le=1)
    vector_match_threshold: float | None = Field(default=None, ge=0, le=1)
    no_match_action: str | None = Field(default=None, pattern=r"^(ALLOW|REVIEW)$")


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    model_version: str
    pack_versions: dict[str, str]
    toxicity_by_action: ToxicityByAction
    allow_label: str
    allow_reason_code: ReasonCode
    allow_confidence: float = Field(ge=0, le=1)
    language_hints: LanguageHints
    electoral_phase: ElectoralPhase | None = None
    deployment_stage: DeploymentStage | None = None
    phase_overrides: dict[ElectoralPhase, PhasePolicyOverride] = Field(
        default_factory=dict
    )


class EffectivePolicyRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: PolicyConfig
    effective_phase: ElectoralPhase | None = None
    effective_deployment_stage: DeploymentStage = DeploymentStage.SUPERVISED
    effective_policy_version: str
    toxicity_by_action: ToxicityByAction
    allow_confidence: float = Field(ge=0, le=1)
    vector_match_threshold: float | None = Field(default=None, ge=0, le=1)
    no_match_action: str = Field(pattern=r"^(ALLOW|REVIEW)$")


def _default_config_path() -> Path:
    module_path = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "config" / "policy" / "default.json",
        module_path.parents[2] / "config" / "policy" / "default.json",
        module_path.parents[1] / "config" / "policy" / "default.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def reset_policy_config_cache() -> None:
    get_policy_config.cache_clear()


@lru_cache(maxsize=1)
def get_policy_config() -> PolicyConfig:
    path = Path(
        os.getenv("SENTINEL_POLICY_CONFIG_PATH", str(_default_config_path()))
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = PolicyConfig.model_validate(payload)
    return config


def _resolve_effective_phase(config: PolicyConfig) -> ElectoralPhase | None:
    env_phase = os.getenv("SENTINEL_ELECTORAL_PHASE")
    if env_phase is None or not env_phase.strip():
        return config.electoral_phase
    try:
        return ElectoralPhase(env_phase.strip())
    except ValueError as exc:
        raise ValueError(
            f"invalid SENTINEL_ELECTORAL_PHASE value: {env_phase}"
        ) from exc


def _resolve_effective_deployment_stage(config: PolicyConfig) -> DeploymentStage:
    env_stage = os.getenv("SENTINEL_DEPLOYMENT_STAGE")
    if env_stage is not None and env_stage.strip():
        try:
            return DeploymentStage(env_stage.strip().lower())
        except ValueError as exc:
            raise ValueError(
                f"invalid SENTINEL_DEPLOYMENT_STAGE value: {env_stage}"
            ) from exc
    if config.deployment_stage is not None:
        return config.deployment_stage
    return DeploymentStage.SUPERVISED


def resolve_policy_runtime(config: PolicyConfig | None = None) -> EffectivePolicyRuntime:
    config = config or get_policy_config()
    effective_phase = _resolve_effective_phase(config)
    effective_deployment_stage = _resolve_effective_deployment_stage(config)
    override = (
        config.phase_overrides.get(effective_phase)
        if effective_phase is not None
        else None
    )
    if override is None:
        toxicity_by_action = config.toxicity_by_action
        allow_confidence = config.allow_confidence
        vector_match_threshold = None
        no_match_action = "ALLOW"
    else:
        toxicity_by_action = override.toxicity_by_action or config.toxicity_by_action
        if toxicity_by_action.BLOCK < config.toxicity_by_action.BLOCK:
            raise ValueError(
                "phase override cannot lower BLOCK toxicity threshold below baseline"
            )
        allow_confidence = (
            config.allow_confidence
            if override.allow_confidence is None
            else override.allow_confidence
        )
        vector_match_threshold = override.vector_match_threshold
        no_match_action = override.no_match_action or "ALLOW"

    effective_policy_version = (
        config.version
        if effective_phase is None
        else f"{config.version}@{effective_phase.value}"
    )
    if effective_deployment_stage != DeploymentStage.SUPERVISED:
        effective_policy_version = (
            f"{effective_policy_version}#{effective_deployment_stage.value}"
        )

    return EffectivePolicyRuntime(
        config=config,
        effective_phase=effective_phase,
        effective_deployment_stage=effective_deployment_stage,
        effective_policy_version=effective_policy_version,
        toxicity_by_action=toxicity_by_action,
        allow_confidence=allow_confidence,
        vector_match_threshold=vector_match_threshold,
        no_match_action=no_match_action,
    )
