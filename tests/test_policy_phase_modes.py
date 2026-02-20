from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

import sentinel_api.policy as policy
from sentinel_api.policy_config import (
    get_policy_config,
    reset_policy_config_cache,
    resolve_policy_runtime,
)


def setup_function() -> None:
    reset_policy_config_cache()


def teardown_function() -> None:
    reset_policy_config_cache()


def test_default_config_includes_all_phase_override_profiles() -> None:
    config = get_policy_config()
    assert {phase.value for phase in config.phase_overrides.keys()} == {
        "pre_campaign",
        "campaign",
        "silence_period",
        "voting_day",
        "results_period",
    }


def test_invalid_phase_env_value_fails_runtime_resolution(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_ELECTORAL_PHASE", "bad-phase")
    with pytest.raises(ValueError, match="invalid SENTINEL_ELECTORAL_PHASE"):
        resolve_policy_runtime()


def test_moderation_policy_version_includes_effective_phase_suffix(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_ELECTORAL_PHASE", "campaign")
    result = policy.moderate("peaceful discussion")
    assert result.policy_version.endswith("@campaign")


def test_silence_period_escalates_no_match_to_review(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_ELECTORAL_PHASE", "silence_period")
    monkeypatch.setattr(
        policy,
        "find_vector_match",
        lambda *_args, **_kwargs: None,
    )
    decision = policy.evaluate_text("peaceful discussion")
    assert decision.action == "REVIEW"
    assert decision.labels == ["DOGWHISTLE_WATCH"]
    assert decision.reason_codes == ["R_DOGWHISTLE_CONTEXT_REQUIRED"]


def test_phase_override_passes_vector_threshold_to_matcher(monkeypatch) -> None:
    captured: dict[str, float | None] = {"threshold": None}

    class _Runtime:
        embedding_provider_id = "hash-bow-v1"

        class _Provider:
            def embed(self, _text: str, *, timeout_ms: int):  # type: ignore[no-untyped-def]
                del timeout_ms
                return [0.1] * 64

        embedding_provider = _Provider()

    def _fake_find_vector_match(
        _text: str,
        *,
        lexicon_version: str,
        query_embedding: list[float],
        embedding_model: str,
        min_similarity=None,
    ):
        del lexicon_version
        del query_embedding, embedding_model
        captured["threshold"] = min_similarity
        return None

    monkeypatch.setenv("SENTINEL_ELECTORAL_PHASE", "voting_day")
    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(policy, "get_model_runtime", lambda: _Runtime())
    monkeypatch.setattr(policy, "find_vector_match", _fake_find_vector_match)
    decision = policy.evaluate_text("peaceful discussion")
    assert decision.action == "REVIEW"
    assert captured["threshold"] == 0.9


def test_unknown_phase_in_config_fails_validation(tmp_path, monkeypatch) -> None:
    bad = {
        "version": "policy-bad-phase",
        "model_version": "sentinel-multi-v2",
        "pack_versions": {"en": "pack-en-0.1"},
        "toxicity_by_action": {"BLOCK": 0.9, "REVIEW": 0.45, "ALLOW": 0.05},
        "allow_label": "BENIGN_POLITICAL_SPEECH",
        "allow_reason_code": "R_ALLOW_NO_POLICY_MATCH",
        "allow_confidence": 0.65,
        "electoral_phase": "unknown_phase",
        "phase_overrides": {},
        "language_hints": {"sw": ["na"], "sh": ["msee"]},
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setenv("SENTINEL_POLICY_CONFIG_PATH", str(path))
    with pytest.raises(ValidationError):
        get_policy_config()


def test_phase_override_cannot_lower_block_toxicity(monkeypatch, tmp_path) -> None:
    cfg = {
        "version": "policy-phase-toxicity-guard",
        "model_version": "sentinel-multi-v2",
        "pack_versions": {"en": "pack-en-0.1"},
        "toxicity_by_action": {"BLOCK": 0.9, "REVIEW": 0.45, "ALLOW": 0.05},
        "allow_label": "BENIGN_POLITICAL_SPEECH",
        "allow_reason_code": "R_ALLOW_NO_POLICY_MATCH",
        "allow_confidence": 0.65,
        "electoral_phase": "campaign",
        "phase_overrides": {
            "campaign": {"toxicity_by_action": {"BLOCK": 0.7, "REVIEW": 0.45, "ALLOW": 0.05}}
        },
        "language_hints": {"sw": ["na"], "sh": ["msee"]},
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("SENTINEL_POLICY_CONFIG_PATH", str(path))
    with pytest.raises(ValueError, match="cannot lower BLOCK toxicity threshold below baseline"):
        resolve_policy_runtime()


def test_invalid_claim_likeness_threshold_order_fails_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cfg = {
        "version": "policy-claim-threshold-order",
        "model_version": "sentinel-multi-v2",
        "pack_versions": {"en": "pack-en-0.1"},
        "toxicity_by_action": {"BLOCK": 0.9, "REVIEW": 0.45, "ALLOW": 0.05},
        "allow_label": "BENIGN_POLITICAL_SPEECH",
        "allow_reason_code": "R_ALLOW_NO_POLICY_MATCH",
        "allow_confidence": 0.65,
        "claim_likeness": {
            "medium_threshold": 0.8,
            "high_threshold": 0.7,
            "require_election_anchor": True,
        },
        "phase_overrides": {},
        "language_hints": {"sw": ["na"], "sh": ["msee"]},
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("SENTINEL_POLICY_CONFIG_PATH", str(path))
    with pytest.raises(ValidationError, match="medium_threshold must be < high_threshold"):
        get_policy_config()
