from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def fail(message: str) -> None:
    print(f"contract-check: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    openapi_path = Path("docs/specs/api/openapi.yaml")
    response_schema_path = Path("docs/specs/schemas/moderation-response.schema.json")
    request_schema_path = Path("docs/specs/schemas/moderation-request.schema.json")
    metrics_schema_path = Path("docs/specs/schemas/metrics-response.schema.json")
    internal_schema_paths = {
        "queue": Path("docs/specs/schemas/internal/monitoring-queue-item.schema.json"),
        "cluster": Path("docs/specs/schemas/internal/monitoring-cluster.schema.json"),
        "proposal": Path("docs/specs/schemas/internal/release-proposal.schema.json"),
        "proposal_review": Path("docs/specs/schemas/internal/proposal-review-event.schema.json"),
        "appeal_request": Path("docs/specs/schemas/internal/appeal-request.schema.json"),
        "appeal_transition": Path(
            "docs/specs/schemas/internal/appeal-state-transition.schema.json"
        ),
        "appeal_resolution": Path("docs/specs/schemas/internal/appeal-resolution.schema.json"),
        "transparency_export_record": Path(
            "docs/specs/schemas/internal/transparency-export-record.schema.json"
        ),
        "transparency_report": Path(
            "docs/specs/schemas/internal/transparency-appeals-report.schema.json"
        ),
        "partner_signal": Path("docs/specs/schemas/internal/partner-connector-signal.schema.json"),
        "partner_ingest_report": Path(
            "docs/specs/schemas/internal/partner-connector-ingest-report.schema.json"
        ),
        "ml_calibration_sample": Path(
            "docs/specs/schemas/internal/ml-calibration-sample.schema.json"
        ),
        "ml_double_annotation_sample": Path(
            "docs/specs/schemas/internal/ml-double-annotation-sample.schema.json"
        ),
    }

    if not openapi_path.exists():
        fail(f"missing {openapi_path}")
    if not response_schema_path.exists():
        fail(f"missing {response_schema_path}")
    if not request_schema_path.exists():
        fail(f"missing {request_schema_path}")
    if not metrics_schema_path.exists():
        fail(f"missing {metrics_schema_path}")
    for schema_path in internal_schema_paths.values():
        if not schema_path.exists():
            fail(f"missing {schema_path}")

    openapi = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
    response_schema = json.loads(response_schema_path.read_text(encoding="utf-8"))
    request_schema = json.loads(request_schema_path.read_text(encoding="utf-8"))
    metrics_schema = json.loads(metrics_schema_path.read_text(encoding="utf-8"))
    internal_schemas = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in internal_schema_paths.items()
    }

    paths = openapi.get("paths", {})
    if "/health" not in paths or "get" not in paths["/health"]:
        fail("openapi missing GET /health")
    if "/metrics" not in paths or "get" not in paths["/metrics"]:
        fail("openapi missing GET /metrics")

    moderate = paths.get("/v1/moderate", {}).get("post")
    if not moderate:
        fail("openapi missing POST /v1/moderate")

    responses = moderate.get("responses", {})
    for code in ("200", "400", "401", "429", "500"):
        if code not in responses:
            fail(f"openapi missing /v1/moderate response {code}")

    required_request = set(
        openapi["components"]["schemas"]["ModerationRequest"].get("required", [])
    )
    if required_request != set(request_schema.get("required", [])):
        fail("request required fields mismatch between openapi and JSON schema")

    required_response = set(
        openapi["components"]["schemas"]["ModerationResponse"].get("required", [])
    )
    if required_response != set(response_schema.get("required", [])):
        fail("response required fields mismatch between openapi and JSON schema")

    required_metrics = set(openapi["components"]["schemas"]["MetricsResponse"].get("required", []))
    if required_metrics != set(metrics_schema.get("required", [])):
        fail("metrics required fields mismatch between openapi and JSON schema")

    for name, schema in internal_schemas.items():
        if schema.get("type") != "object":
            fail(f"internal schema {name} must be object")
        if schema.get("additionalProperties") is not False:
            fail(f"internal schema {name} must set additionalProperties=false")
        if "$schema" not in schema:
            fail(f"internal schema {name} missing $schema")
        if not schema.get("required"):
            fail(f"internal schema {name} missing required fields")

    queue_priority = set(internal_schemas["queue"]["properties"]["priority"].get("enum", []))
    if queue_priority != {"critical", "urgent", "standard", "batch"}:
        fail("internal queue priority enum mismatch")

    queue_state = set(internal_schemas["queue"]["properties"]["state"].get("enum", []))
    if queue_state != {
        "queued",
        "processing",
        "clustered",
        "proposed",
        "dropped",
        "error",
    }:
        fail("internal queue state enum mismatch")

    proposal_type = set(internal_schemas["proposal"]["properties"]["proposal_type"].get("enum", []))
    if proposal_type != {"lexicon", "narrative", "policy"}:
        fail("internal proposal_type enum mismatch")

    proposal_status = set(internal_schemas["proposal"]["properties"]["status"].get("enum", []))
    if proposal_status != {
        "draft",
        "in_review",
        "needs_revision",
        "approved",
        "promoted",
        "rejected",
    }:
        fail("internal proposal status enum mismatch")

    review_action = set(internal_schemas["proposal_review"]["properties"]["action"].get("enum", []))
    if review_action != {
        "submit_review",
        "approve",
        "reject",
        "request_changes",
        "promote",
    }:
        fail("internal proposal review action enum mismatch")

    appeal_action = set(
        internal_schemas["appeal_request"]["properties"]["original_action"].get("enum", [])
    )
    if appeal_action != {"ALLOW", "REVIEW", "BLOCK"}:
        fail("internal appeal request original_action enum mismatch")

    appeal_transition_status = set(
        internal_schemas["appeal_transition"]["properties"]["to_status"].get("enum", [])
    )
    if appeal_transition_status != {
        "submitted",
        "triaged",
        "in_review",
        "rejected_invalid",
        "resolved_upheld",
        "resolved_reversed",
        "resolved_modified",
    }:
        fail("internal appeal transition status enum mismatch")

    appeal_resolution_status = set(
        internal_schemas["appeal_resolution"]["properties"]["status"].get("enum", [])
    )
    if appeal_resolution_status != {
        "resolved_upheld",
        "resolved_reversed",
        "resolved_modified",
    }:
        fail("internal appeal resolution status enum mismatch")

    transparency_record_status = set(
        internal_schemas["transparency_export_record"]["properties"]["status"].get("enum", [])
    )
    if transparency_record_status != {
        "submitted",
        "triaged",
        "in_review",
        "rejected_invalid",
        "resolved_upheld",
        "resolved_reversed",
        "resolved_modified",
    }:
        fail("internal transparency export record status enum mismatch")

    transparency_record_action = set(
        internal_schemas["transparency_export_record"]["properties"]["original_action"].get(
            "enum", []
        )
    )
    if transparency_record_action != {"ALLOW", "REVIEW", "BLOCK"}:
        fail("internal transparency export record original_action enum mismatch")

    transparency_resolution_status = set(
        internal_schemas["transparency_export_record"]["properties"]["resolution_status"].get(
            "enum", []
        )
    )
    if transparency_resolution_status != {
        "resolved_upheld",
        "resolved_reversed",
        "resolved_modified",
        None,
    }:
        fail("internal transparency export record resolution_status enum mismatch")

    partner_manual_priority = set(
        internal_schemas["partner_signal"]["properties"]["manual_priority"].get("enum", [])
    )
    if partner_manual_priority != {"critical", "urgent", "standard", "batch"}:
        fail("internal partner signal manual_priority enum mismatch")

    partner_ingest_status = set(
        internal_schemas["partner_ingest_report"]["properties"]["status"].get("enum", [])
    )
    if partner_ingest_status != {"ok", "error", "circuit_open"}:
        fail("internal partner ingest report status enum mismatch")

    ml_language_enum = set(
        internal_schemas["ml_calibration_sample"]["properties"]["language"].get("enum", [])
    )
    if ml_language_enum != {"en", "sw", "sh"}:
        fail("internal ml calibration language enum mismatch")

    ml_double_language_enum = set(
        internal_schemas["ml_double_annotation_sample"]["properties"]["language"].get("enum", [])
    )
    if ml_double_language_enum != {"en", "sw", "sh"}:
        fail("internal ml double-annotation language enum mismatch")

    expected_retention_classes = {
        "operational_runtime",
        "async_monitoring_raw",
        "decision_record",
        "governance_audit",
        "analytics_aggregate",
        "legal_hold",
    }
    for schema_name in ("queue", "cluster", "proposal", "proposal_review"):
        properties = internal_schemas[schema_name]["properties"]
        retention_enum = set(properties["retention_class"].get("enum", []))
        if retention_enum != expected_retention_classes:
            fail(f"internal {schema_name} retention_class enum mismatch")
        legal_hold_type = properties["legal_hold"].get("type")
        if legal_hold_type != "boolean":
            fail(f"internal {schema_name} legal_hold type mismatch")

    print("contract-check: ok")


if __name__ == "__main__":
    main()
