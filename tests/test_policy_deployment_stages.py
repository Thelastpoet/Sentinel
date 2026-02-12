from __future__ import annotations

import pytest

from sentinel_api.policy import moderate
from sentinel_api.policy_config import reset_policy_config_cache, resolve_policy_runtime


def setup_function() -> None:
    reset_policy_config_cache()


def teardown_function() -> None:
    reset_policy_config_cache()


def test_invalid_deployment_stage_env_value_fails_runtime_resolution(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "invalid")
    with pytest.raises(ValueError, match="invalid SENTINEL_DEPLOYMENT_STAGE"):
        resolve_policy_runtime()


def test_default_deployment_stage_is_supervised_without_suffix(monkeypatch) -> None:
    monkeypatch.delenv("SENTINEL_DEPLOYMENT_STAGE", raising=False)
    runtime = resolve_policy_runtime()
    assert runtime.effective_deployment_stage.value == "supervised"
    result = moderate("peaceful discussion")
    assert "#" not in result.policy_version


def test_policy_version_includes_stage_suffix_for_non_supervised(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "advisory")
    result = moderate("peaceful discussion")
    assert result.policy_version.endswith("#advisory")


def test_policy_version_includes_phase_and_stage_suffix(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_ELECTORAL_PHASE", "campaign")
    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "advisory")
    result = moderate("peaceful discussion")
    assert result.policy_version.endswith("@campaign#advisory")


def test_advisory_stage_downgrades_block_to_review(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "advisory")
    result = moderate("They should kill them now.")
    assert result.action == "REVIEW"
    assert "INCITEMENT_VIOLENCE" in result.labels
    assert "R_STAGE_ADVISORY_BLOCK_DOWNGRADED" in result.reason_codes


def test_shadow_stage_forces_allow_for_harmful_content(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "shadow")
    result = moderate("They should kill them now.")
    assert result.action == "ALLOW"
    assert "INCITEMENT_VIOLENCE" in result.labels
    assert "R_STAGE_SHADOW_NO_ENFORCE" in result.reason_codes


def test_supervised_stage_preserves_block(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_DEPLOYMENT_STAGE", "supervised")
    result = moderate("They should kill them now.")
    assert result.action == "BLOCK"
    assert "R_STAGE_ADVISORY_BLOCK_DOWNGRADED" not in result.reason_codes
    assert "R_STAGE_SHADOW_NO_ENFORCE" not in result.reason_codes
