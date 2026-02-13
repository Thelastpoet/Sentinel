from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ALLOWED_DECISIONS = {"GO", "NO_GO"}
ALLOWED_LAUNCH_PROFILES = {"baseline_deterministic", "ml_enforced"}
ALLOWED_CHECK_STATUS = {"pass", "fail"}
ALLOWED_SECTION20_DISPOSITIONS = {
    "accepted_for_launch",
    "deferred_blocker",
    "deferred_non_blocker",
}
REQUIRED_SIGNOFF_ROLES = {
    "engineering_lead",
    "safety_governance_lead",
    "security_lead",
    "legal_policy_owner",
}
REQUIRED_BUNDLE_FILES = {
    "decision.json",
    "reliability_latency.json",
    "safety_quality.json",
    "security_controls.json",
    "legal_governance.json",
    "operational_readiness.json",
    "section20_dispositions.json",
    "signoffs.json",
}
REQUIRED_CRITICAL_CHECKS = {
    "latency_gate",
    "security_findings",
    "safety_regressions",
    "evidence_completeness",
}
ML_PREREQUISITE_TASKS = (
    "i413",
    "i414",
    "i415",
    "i416",
    "i417",
    "i418",
    "i419",
    "i420",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Sentinel go-live evidence bundle completeness and decision safety."
    )
    parser.add_argument(
        "--bundle-dir",
        required=True,
        help="Directory path to releases/go-live/<release-id> evidence bundle.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable validator result.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_section20_decision_id(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if re.match(r"^i-?\d+$", normalized):
        if normalized.startswith("i-"):
            return normalized
        return f"i-{normalized[1:]}"
    return normalized


def _validate_section20_dispositions(
    dispositions: object,
) -> tuple[list[str], bool, dict[str, str]]:
    errors: list[str] = []
    has_blocker = False
    normalized_dispositions: dict[str, str] = {}
    if not isinstance(dispositions, list):
        return (
            ["section20_dispositions.json must contain a JSON array"],
            True,
            normalized_dispositions,
        )

    for index, item in enumerate(dispositions):
        if not isinstance(item, dict):
            errors.append(f"section20_dispositions[{index}] must be an object")
            continue
        for key in ("decision_id", "owner", "rationale"):
            if not str(item.get(key, "")).strip():
                errors.append(f"section20_dispositions[{index}] missing {key}")
        disposition = str(item.get("disposition", "")).strip()
        if disposition not in ALLOWED_SECTION20_DISPOSITIONS:
            errors.append(f"section20_dispositions[{index}] has invalid disposition: {disposition}")
            continue
        decision_id = str(item.get("decision_id", "")).strip()
        if decision_id:
            normalized_id = _normalize_section20_decision_id(decision_id)
            if normalized_id in normalized_dispositions:
                errors.append(f"section20_dispositions has duplicate decision_id: {decision_id}")
            else:
                normalized_dispositions[normalized_id] = disposition
        if disposition == "deferred_blocker":
            has_blocker = True
        if disposition == "deferred_non_blocker":
            if not str(item.get("mitigation", "")).strip():
                errors.append(f"section20_dispositions[{index}] missing mitigation")
            if not str(item.get("target_resolution_date", "")).strip():
                errors.append(f"section20_dispositions[{index}] missing target_resolution_date")
    return errors, has_blocker, normalized_dispositions


def _validate_signoffs(signoffs_payload: object) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    found_roles: set[str] = set()

    if not isinstance(signoffs_payload, list):
        return ["signoffs.json must contain a JSON array"], found_roles

    for index, item in enumerate(signoffs_payload):
        if not isinstance(item, dict):
            errors.append(f"signoffs[{index}] must be an object")
            continue
        role = str(item.get("role", "")).strip()
        signer = str(item.get("signer", "")).strip()
        signed_at = str(item.get("signed_at", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        evidence_refs = item.get("evidence_refs")
        if not role:
            errors.append(f"signoffs[{index}] missing role")
            continue
        found_roles.add(role)
        if not signer:
            errors.append(f"signoffs[{index}] missing signer")
        if not signed_at:
            errors.append(f"signoffs[{index}] missing signed_at")
        if not rationale:
            errors.append(f"signoffs[{index}] missing rationale")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f"signoffs[{index}] missing evidence_refs")
    return errors, found_roles


def validate_bundle(bundle_dir: Path) -> dict[str, object]:
    errors: list[str] = []
    missing_files = sorted(
        filename for filename in REQUIRED_BUNDLE_FILES if not (bundle_dir / filename).exists()
    )
    if missing_files:
        return {
            "ok": False,
            "computed_decision": "NO_GO",
            "errors": [f"missing required files: {', '.join(missing_files)}"],
        }

    decision_payload = _load_json(bundle_dir / "decision.json")
    section20_payload = _load_json(bundle_dir / "section20_dispositions.json")
    signoffs_payload = _load_json(bundle_dir / "signoffs.json")

    if not isinstance(decision_payload, dict):
        return {
            "ok": False,
            "computed_decision": "NO_GO",
            "errors": ["decision.json must contain a JSON object"],
        }

    for required in (
        "release_id",
        "generated_at",
        "decision",
        "launch_profile",
        "prerequisites",
        "critical_checks",
    ):
        if required not in decision_payload:
            errors.append(f"decision.json missing {required}")

    stated_decision = str(decision_payload.get("decision", "")).strip()
    if stated_decision not in ALLOWED_DECISIONS:
        errors.append(f"decision.json has invalid decision value: {stated_decision}")
    launch_profile = str(decision_payload.get("launch_profile", "")).strip().lower()
    if launch_profile not in ALLOWED_LAUNCH_PROFILES:
        errors.append(
            f"decision.json launch_profile must be one of {sorted(ALLOWED_LAUNCH_PROFILES)}"
        )

    prerequisites = decision_payload.get("prerequisites")
    if not isinstance(prerequisites, dict):
        errors.append("decision.json prerequisites must be an object")
        prerequisites = {}

    for task_id in ("i409", "i410"):
        task_payload = prerequisites.get(task_id)
        if not isinstance(task_payload, dict):
            errors.append(f"decision.json prerequisites missing {task_id}")
            continue
        task_status = str(task_payload.get("status", "")).strip().lower()
        if task_status != "pass":
            status_text = task_status or "missing"
            errors.append(f"prerequisite {task_id} not satisfied (status={status_text})")
        artifacts = task_payload.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"prerequisite {task_id} missing artifacts")

    critical_checks = decision_payload.get("critical_checks")
    if not isinstance(critical_checks, dict):
        errors.append("decision.json critical_checks must be an object")
        critical_checks = {}

    critical_failures = False
    for check_name in REQUIRED_CRITICAL_CHECKS:
        check_status = str(critical_checks.get(check_name, "")).strip().lower()
        if check_status not in ALLOWED_CHECK_STATUS:
            errors.append(
                f"critical_check {check_name} must be one of {sorted(ALLOWED_CHECK_STATUS)}"
            )
            continue
        if check_status == "fail":
            critical_failures = True

    section20_result = _validate_section20_dispositions(section20_payload)
    section20_errors, section20_has_blocker, normalized_section20 = section20_result
    errors.extend(section20_errors)
    if section20_has_blocker:
        errors.append("section20 dispositions include deferred_blocker")

    if launch_profile == "ml_enforced":
        ml_prerequisites = decision_payload.get("ml_prerequisites")
        if not isinstance(ml_prerequisites, dict):
            errors.append(
                "decision.json ml_prerequisites must be an object for launch_profile=ml_enforced"
            )
        else:
            for task_id in ML_PREREQUISITE_TASKS:
                task_payload = ml_prerequisites.get(task_id)
                if not isinstance(task_payload, dict):
                    errors.append(f"ml_prerequisite {task_id} missing")
                    continue
                task_status = str(task_payload.get("status", "")).strip().lower()
                if task_status != "pass":
                    status_text = task_status or "missing"
                    errors.append(f"ml_prerequisite {task_id} not satisfied (status={status_text})")
                artifacts = task_payload.get("artifacts")
                if not isinstance(artifacts, list) or not artifacts:
                    errors.append(f"ml_prerequisite {task_id} missing artifacts")
                disposition = normalized_section20.get(task_id.replace("i", "i-", 1))
                if disposition and disposition != "accepted_for_launch":
                    errors.append(
                        f"ml_enforced profile cannot defer {task_id.replace('i', 'I-', 1)} "
                        f"(disposition={disposition})"
                    )
    elif launch_profile == "baseline_deterministic":
        for task_id in ML_PREREQUISITE_TASKS:
            section20_id = task_id.replace("i", "i-", 1)
            if section20_id not in normalized_section20:
                errors.append(
                    "baseline_deterministic profile missing Section20 disposition for "
                    f"{task_id.replace('i', 'I-', 1)}"
                )

    signoff_errors, found_roles = _validate_signoffs(signoffs_payload)
    errors.extend(signoff_errors)
    missing_roles = sorted(REQUIRED_SIGNOFF_ROLES - found_roles)
    if missing_roles:
        errors.append(f"missing required sign-off roles: {', '.join(missing_roles)}")

    computed_decision = "GO"
    if errors or critical_failures or section20_has_blocker:
        computed_decision = "NO_GO"

    if stated_decision in ALLOWED_DECISIONS and stated_decision != computed_decision:
        errors.append(
            "decision.json decision mismatch: "
            f"stated={stated_decision} computed={computed_decision}"
        )

    return {
        "ok": not errors,
        "computed_decision": computed_decision,
        "errors": errors,
    }


def main() -> None:
    args = parse_args()
    bundle_dir = Path(args.bundle_dir)
    result = validate_bundle(bundle_dir)

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        if result["ok"]:
            print(f"go-live-check: ok decision={result['computed_decision']}")
        else:
            print(f"go-live-check: failed decision={result['computed_decision']}")
            error_items = result.get("errors")
            if isinstance(error_items, list):
                for err in error_items:
                    print(f"- {err}")
            else:
                print("- missing error details")

    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
