from __future__ import annotations

import json
from pathlib import Path

from scripts.check_go_live_readiness import validate_bundle

ML_TASK_IDS = ("I-413", "I-414", "I-415", "I-416", "I-417", "I-418", "I-419", "I-420")


def _write_bundle(
    path: Path,
    *,
    launch_profile: str = "baseline_deterministic",
    with_blocker: bool = False,
    with_i410: bool = True,
    with_ml_prerequisites: bool = True,
    missing_ml_prerequisite: str | None = None,
    with_ml_dispositions: bool = True,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "reliability_latency.json").write_text("{}", encoding="utf-8")
    (path / "safety_quality.json").write_text("{}", encoding="utf-8")
    (path / "security_controls.json").write_text("{}", encoding="utf-8")
    (path / "legal_governance.json").write_text("{}", encoding="utf-8")
    (path / "operational_readiness.json").write_text("{}", encoding="utf-8")

    section20 = [
        {
            "decision_id": "S20-01",
            "disposition": "accepted_for_launch",
            "owner": "platform-lead",
            "rationale": "governance approved",
        }
    ]
    if with_ml_dispositions:
        for task_id in ML_TASK_IDS:
            section20.append(
                {
                    "decision_id": task_id,
                    "disposition": "deferred_non_blocker",
                    "owner": "platform-lead",
                    "rationale": "deferred under baseline profile",
                    "mitigation": "deterministic controls remain active",
                    "target_resolution_date": "2026-12-31",
                }
            )
    if with_blocker:
        section20.append(
            {
                "decision_id": "S20-02",
                "disposition": "deferred_blocker",
                "owner": "security-lead",
                "rationale": "open blocker",
            }
        )
    (path / "section20_dispositions.json").write_text(
        json.dumps(section20, sort_keys=True),
        encoding="utf-8",
    )

    signoffs = [
        {
            "role": "engineering_lead",
            "signer": "eng-1",
            "signed_at": "2026-02-13T00:00:00+00:00",
            "rationale": "approved",
            "evidence_refs": ["reliability_latency.json"],
        },
        {
            "role": "safety_governance_lead",
            "signer": "safety-1",
            "signed_at": "2026-02-13T00:00:00+00:00",
            "rationale": "approved",
            "evidence_refs": ["safety_quality.json"],
        },
        {
            "role": "security_lead",
            "signer": "sec-1",
            "signed_at": "2026-02-13T00:00:00+00:00",
            "rationale": "approved",
            "evidence_refs": ["security_controls.json"],
        },
        {
            "role": "legal_policy_owner",
            "signer": "legal-1",
            "signed_at": "2026-02-13T00:00:00+00:00",
            "rationale": "approved",
            "evidence_refs": ["legal_governance.json"],
        },
    ]
    (path / "signoffs.json").write_text(json.dumps(signoffs, sort_keys=True), encoding="utf-8")

    prerequisites = {
        "i409": {"status": "pass", "artifacts": ["ci-lint-typecheck.log"]},
        "i410": {"status": "pass", "artifacts": ["latency-benchmark.json"]},
    }
    if not with_i410:
        prerequisites["i410"] = {"status": "fail", "artifacts": []}

    ml_prerequisites: dict[str, object] = {}
    if with_ml_prerequisites:
        for task_id in ("i413", "i414", "i415", "i416", "i417", "i418", "i419", "i420"):
            if missing_ml_prerequisite and missing_ml_prerequisite == task_id:
                continue
            ml_prerequisites[task_id] = {
                "status": "pass",
                "artifacts": [f"{task_id}-evidence.json"],
            }

    should_be_go = (
        not with_blocker
        and with_i410
        and (
            launch_profile != "ml_enforced"
            or (with_ml_prerequisites and missing_ml_prerequisite is None)
        )
        and (launch_profile != "baseline_deterministic" or with_ml_dispositions)
    )
    decision = {
        "release_id": "2026-02-13-v1",
        "generated_at": "2026-02-13T00:00:00+00:00",
        "decision": "GO" if should_be_go else "NO_GO",
        "launch_profile": launch_profile,
        "prerequisites": prerequisites,
        "critical_checks": {
            "latency_gate": "pass",
            "security_findings": "pass",
            "safety_regressions": "pass",
            "evidence_completeness": "pass",
        },
    }
    if launch_profile == "ml_enforced":
        decision["ml_prerequisites"] = ml_prerequisites
    (path / "decision.json").write_text(json.dumps(decision, sort_keys=True), encoding="utf-8")


def test_validate_bundle_passes_for_complete_go_bundle(tmp_path) -> None:
    bundle = tmp_path / "go-live"
    _write_bundle(bundle)
    result = validate_bundle(bundle)
    assert result["ok"] is True
    assert result["computed_decision"] == "GO"


def test_validate_bundle_fails_when_prerequisite_missing(tmp_path) -> None:
    bundle = tmp_path / "go-live"
    _write_bundle(bundle, with_i410=False)
    result = validate_bundle(bundle)
    assert result["ok"] is False
    assert result["computed_decision"] == "NO_GO"
    errors = result.get("errors")
    assert isinstance(errors, list)
    assert any("i410" in str(item) for item in errors)


def test_validate_bundle_fails_when_section20_has_blocker(tmp_path) -> None:
    bundle = tmp_path / "go-live"
    _write_bundle(bundle, with_blocker=True)
    result = validate_bundle(bundle)
    assert result["ok"] is False
    assert result["computed_decision"] == "NO_GO"


def test_validate_bundle_ml_enforced_requires_ml_prerequisites(tmp_path) -> None:
    bundle = tmp_path / "go-live"
    _write_bundle(
        bundle,
        launch_profile="ml_enforced",
        with_ml_dispositions=False,
    )
    result = validate_bundle(bundle)
    assert result["ok"] is True
    assert result["computed_decision"] == "GO"


def test_validate_bundle_ml_enforced_fails_when_ml_prerequisite_missing(tmp_path) -> None:
    bundle = tmp_path / "go-live"
    _write_bundle(
        bundle,
        launch_profile="ml_enforced",
        with_ml_dispositions=False,
        missing_ml_prerequisite="i420",
    )
    result = validate_bundle(bundle)
    assert result["ok"] is False
    assert result["computed_decision"] == "NO_GO"
    errors = result.get("errors")
    assert isinstance(errors, list)
    assert any("i420" in str(item) for item in errors)


def test_validate_bundle_baseline_requires_ml_dispositions(tmp_path) -> None:
    bundle = tmp_path / "go-live"
    _write_bundle(
        bundle,
        launch_profile="baseline_deterministic",
        with_ml_dispositions=False,
    )
    result = validate_bundle(bundle)
    assert result["ok"] is False
    assert result["computed_decision"] == "NO_GO"
    errors = result.get("errors")
    assert isinstance(errors, list)
    assert any("I-413" in str(item) for item in errors)
