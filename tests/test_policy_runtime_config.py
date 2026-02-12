from __future__ import annotations

import json

from sentinel_api.policy import moderate
from sentinel_api.policy_config import reset_policy_config_cache


def test_moderation_uses_external_policy_config(tmp_path, monkeypatch) -> None:
    cfg = {
        "version": "policy-2099.01",
        "model_version": "sentinel-multi-custom",
        "pack_versions": {"en": "pack-en-9.9"},
        "toxicity_by_action": {"BLOCK": 0.99, "REVIEW": 0.55, "ALLOW": 0.01},
        "allow_label": "BENIGN_POLITICAL_SPEECH",
        "allow_reason_code": "R_ALLOW_NO_POLICY_MATCH",
        "allow_confidence": 0.9,
        "language_hints": {"sw": ["na"], "sh": ["msee"]},
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")

    monkeypatch.setenv("SENTINEL_POLICY_CONFIG_PATH", str(path))
    reset_policy_config_cache()
    result = moderate("peaceful discussion")
    assert result.policy_version == "policy-2099.01"
    assert result.model_version == "sentinel-multi-custom"
    assert result.toxicity == 0.01
    assert result.pack_versions["en"] == "pack-en-9.9"
    reset_policy_config_cache()

