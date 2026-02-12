from __future__ import annotations

import json
import os
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
