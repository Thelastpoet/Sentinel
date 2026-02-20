"""Compatibility shim for policy configuration primitives.

This module preserves existing imports during staged package extraction.
Prefer importing from `sentinel_core.policy_config` for new code.
"""

from sentinel_core.policy_config import (  # noqa: F401
    ClaimLikenessConfig,
    EffectivePolicyRuntime,
    ElectoralPhase,
    LanguageHints,
    PhasePolicyOverride,
    PolicyConfig,
    ReasonCode,
    ToxicityByAction,
    get_policy_config,
    get_runtime_phase_override,
    reset_policy_config_cache,
    resolve_policy_runtime,
    set_runtime_phase_override,
)
