from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from sentinel_api.policy_config import (
    get_policy_config,
    reset_policy_config_cache,
    resolve_policy_runtime,
)


def setup_function() -> None:
    reset_policy_config_cache()


def teardown_function() -> None:
    reset_policy_config_cache()


def test_default_policy_config_loads(monkeypatch) -> None:
    monkeypatch.delenv("SENTINEL_POLICY_CONFIG_PATH", raising=False)
    monkeypatch.delenv("SENTINEL_ELECTORAL_PHASE", raising=False)
    config = get_policy_config()
    assert config.version == "policy-2026.11"
    assert config.model_version == "sentinel-multi-v2"
    assert config.toxicity_by_action.BLOCK == 0.9
    assert config.deployment_stage is None


def test_config_deployment_stage_applies_when_env_unset(tmp_path, monkeypatch) -> None:
    cfg = {
        "version": "policy-stage-test",
        "model_version": "sentinel-multi-v2",
        "pack_versions": {"en": "pack-en-0.1"},
        "toxicity_by_action": {"BLOCK": 0.9, "REVIEW": 0.45, "ALLOW": 0.05},
        "allow_label": "BENIGN_POLITICAL_SPEECH",
        "allow_reason_code": "R_ALLOW_NO_POLICY_MATCH",
        "allow_confidence": 0.65,
        "deployment_stage": "advisory",
        "language_hints": {"sw": ["na"], "sh": ["msee"]},
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("SENTINEL_POLICY_CONFIG_PATH", str(path))
    monkeypatch.delenv("SENTINEL_DEPLOYMENT_STAGE", raising=False)
    runtime = resolve_policy_runtime()
    assert runtime.effective_deployment_stage.value == "advisory"


def test_invalid_policy_config_fails_validation(tmp_path, monkeypatch) -> None:
    bad = {
        "version": "policy-bad",
        "model_version": "sentinel-multi-v2",
        "pack_versions": {"en": "pack-en-0.1"},
        "toxicity_by_action": {"BLOCK": 1.2, "REVIEW": 0.4, "ALLOW": 0.1},
        "allow_label": "BENIGN_POLITICAL_SPEECH",
        "allow_reason_code": "bad_reason",
        "allow_confidence": 0.5,
        "language_hints": {"sw": ["na"], "sh": ["msee"]},
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setenv("SENTINEL_POLICY_CONFIG_PATH", str(path))

    with pytest.raises(ValidationError):
        get_policy_config()


def test_default_policy_config_path_uses_cwd_when_available(tmp_path, monkeypatch) -> None:
    cfg = {
        "version": "policy-cwd-test",
        "model_version": "sentinel-multi-v2",
        "pack_versions": {
            "en": "pack-en-0.1",
            "sw": "pack-sw-0.1",
            "sh": "pack-sh-0.1",
        },
        "toxicity_by_action": {"BLOCK": 0.9, "REVIEW": 0.45, "ALLOW": 0.05},
        "allow_label": "BENIGN_POLITICAL_SPEECH",
        "allow_reason_code": "R_ALLOW_NO_POLICY_MATCH",
        "allow_confidence": 0.65,
        "language_hints": {"sw": ["na"], "sh": ["msee"]},
    }
    policy_dir = tmp_path / "config" / "policy"
    policy_dir.mkdir(parents=True)
    (policy_dir / "default.json").write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SENTINEL_POLICY_CONFIG_PATH", raising=False)
    monkeypatch.delenv("SENTINEL_ELECTORAL_PHASE", raising=False)

    config = get_policy_config()
    assert config.version == "policy-cwd-test"
