from __future__ import annotations

import json
from pathlib import Path

from scripts.check_go_live_readiness import validate_bundle


def _write_bundle(path: Path, *, with_blocker: bool = False, with_i410: bool = True) -> None:
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

    decision = {
        "release_id": "2026-02-13-v1",
        "generated_at": "2026-02-13T00:00:00+00:00",
        "decision": "NO_GO" if with_blocker or not with_i410 else "GO",
        "prerequisites": prerequisites,
        "critical_checks": {
            "latency_gate": "pass",
            "security_findings": "pass",
            "safety_regressions": "pass",
            "evidence_completeness": "pass",
        },
    }
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
    assert any("i410" in item for item in result["errors"])


def test_validate_bundle_fails_when_section20_has_blocker(tmp_path) -> None:
    bundle = tmp_path / "go-live"
    _write_bundle(bundle, with_blocker=True)
    result = validate_bundle(bundle)
    assert result["ok"] is False
    assert result["computed_decision"] == "NO_GO"
