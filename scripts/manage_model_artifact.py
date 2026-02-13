from __future__ import annotations

import argparse
import importlib
import json
import os
import re

from sentinel_core.async_state_machine import (
    InvalidStateTransition,
    validate_model_artifact_transition,
)

SHA256_PATTERN = re.compile(r"^[A-Fa-f0-9]{64}$")
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,128}$")
VALID_MODEL_STATUSES = {"draft", "validated", "active", "deprecated", "revoked"}
RETENTION_CLASS_DECISION_RECORD = "decision_record"
RETENTION_CLASS_GOVERNANCE_AUDIT = "governance_audit"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Manage model artifact lifecycle "
            "(register/validate/activate/deprecate/revoke/rollback)."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("SENTINEL_DATABASE_URL"),
        help="Postgres connection URL. Defaults to SENTINEL_DATABASE_URL.",
    )
    parser.add_argument(
        "--actor",
        default=os.getenv("SENTINEL_MODEL_ARTIFACT_ACTOR", os.getenv("USER", "system")),
        help="Actor identifier for audit records.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register", help="Register a draft model artifact.")
    register.add_argument("--model-id", required=True)
    register.add_argument("--artifact-uri", required=True)
    register.add_argument("--sha256", required=True)
    register.add_argument("--dataset-ref", required=True)
    register.add_argument("--metrics-ref", required=True)
    register.add_argument(
        "--compatibility-json",
        default="{}",
        help="JSON object with runtime compatibility constraints.",
    )
    register.add_argument("--notes", default=None)

    validate = subparsers.add_parser(
        "validate",
        help="Validate and promote draft artifact to validated.",
    )
    validate.add_argument("--model-id", required=True)
    validate.add_argument("--notes", default=None)

    activate = subparsers.add_parser(
        "activate",
        help="Activate a validated/deprecated model artifact.",
    )
    activate.add_argument("--model-id", required=True)
    activate.add_argument("--notes", default=None)

    deprecate = subparsers.add_parser(
        "deprecate",
        help="Deprecate an active/validated model artifact.",
    )
    deprecate.add_argument("--model-id", required=True)
    deprecate.add_argument("--notes", default=None)

    revoke = subparsers.add_parser("revoke", help="Revoke a model artifact.")
    revoke.add_argument("--model-id", required=True)
    revoke.add_argument("--notes", default=None)

    rollback = subparsers.add_parser(
        "rollback",
        help="Rollback active artifact to previous active candidate.",
    )
    rollback.add_argument(
        "--to-model-id",
        default=None,
        help="Optional explicit rollback target. Defaults to most recent deprecated artifact.",
    )
    rollback.add_argument("--notes", default=None)

    subparsers.add_parser("list", help="List model artifacts.")

    audit = subparsers.add_parser("audit", help="List model artifact audit events.")
    audit.add_argument("--model-id", default=None)
    audit.add_argument("--limit", type=int, default=20)

    active = subparsers.add_parser("active", help="Show active model artifact.")
    active.add_argument("--json", action="store_true")
    return parser.parse_args()


def _normalize_model_id(value: str) -> str:
    normalized = value.strip()
    if not MODEL_ID_PATTERN.match(normalized):
        raise ValueError("model_id must match ^[A-Za-z0-9._-]{3,128}$")
    return normalized


def _normalize_required_text(value: str, *, field_name: str, max_length: int = 512) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} exceeds max length {max_length}")
    return normalized


def _normalize_sha256(value: str) -> str:
    normalized = value.strip()
    if not SHA256_PATTERN.match(normalized):
        raise ValueError("sha256 must be a 64-character hex string")
    return normalized.lower()


def _parse_compatibility_json(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("compatibility-json must be valid JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("compatibility-json must be a JSON object")
    return json.dumps(payload, sort_keys=True)


def write_model_artifact_audit(
    cur,
    *,
    model_id: str,
    from_status: str | None,
    to_status: str,
    action: str,
    actor: str,
    details: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO model_artifact_audit
          (
            model_id, from_status, to_status, action, actor, details,
            retention_class, legal_hold
          )
        VALUES
          (%s, %s, %s, %s, %s, %s, %s, FALSE)
        """,
        (
            model_id,
            from_status,
            to_status,
            action,
            actor,
            details,
            RETENTION_CLASS_GOVERNANCE_AUDIT,
        ),
    )


def get_model_artifact_status(cur, model_id: str, *, for_update: bool = False) -> str | None:
    query = "SELECT status FROM model_artifacts WHERE model_id = %s"
    if for_update:
        query += " FOR UPDATE"
    cur.execute(query, (model_id,))
    row = cur.fetchone()
    if row is None:
        return None
    return str(row[0])


def get_model_artifact_legal_hold(cur, model_id: str) -> bool | None:
    cur.execute("SELECT legal_hold FROM model_artifacts WHERE model_id = %s", (model_id,))
    row = cur.fetchone()
    if row is None:
        return None
    return bool(row[0])


def get_active_model_id(
    cur,
    *,
    exclude_model_id: str | None = None,
    for_update: bool = False,
) -> str | None:
    query = """
        SELECT model_id
        FROM model_artifacts
        WHERE status = 'active'
    """
    params: tuple[str, ...] | tuple[()] = ()
    if exclude_model_id is not None:
        query += " AND model_id <> %s"
        params = (exclude_model_id,)
    query += " ORDER BY activated_at DESC NULLS LAST, updated_at DESC, model_id DESC LIMIT 1"
    if for_update:
        query += " FOR UPDATE"
    cur.execute(query, params)
    row = cur.fetchone()
    if row is None:
        return None
    return str(row[0])


def register_model_artifact(
    cur,
    *,
    model_id: str,
    artifact_uri: str,
    sha256: str,
    dataset_ref: str,
    metrics_ref: str,
    compatibility_json: str,
    notes: str | None,
    actor: str,
) -> None:
    normalized_model_id = _normalize_model_id(model_id)
    normalized_uri = _normalize_required_text(artifact_uri, field_name="artifact_uri")
    normalized_sha = _normalize_sha256(sha256)
    normalized_dataset_ref = _normalize_required_text(dataset_ref, field_name="dataset_ref")
    normalized_metrics_ref = _normalize_required_text(metrics_ref, field_name="metrics_ref")
    normalized_compatibility = _parse_compatibility_json(compatibility_json)

    cur.execute(
        """
        INSERT INTO model_artifacts
          (
            model_id, artifact_uri, sha256, dataset_ref, metrics_ref,
            compatibility, status, notes, created_by, retention_class, legal_hold
          )
        VALUES
          (%s, %s, %s, %s, %s, %s::jsonb, 'draft', %s, %s, %s, FALSE)
        ON CONFLICT (model_id) DO NOTHING
        """,
        (
            normalized_model_id,
            normalized_uri,
            normalized_sha,
            normalized_dataset_ref,
            normalized_metrics_ref,
            normalized_compatibility,
            notes,
            actor,
            RETENTION_CLASS_DECISION_RECORD,
        ),
    )
    if cur.rowcount == 0:
        raise ValueError(f"model artifact already exists: {normalized_model_id}")
    write_model_artifact_audit(
        cur,
        model_id=normalized_model_id,
        from_status=None,
        to_status="draft",
        action="register",
        actor=actor,
        details=f"artifact_uri={normalized_uri} notes={notes}",
    )


def _set_model_status(
    cur,
    *,
    model_id: str,
    to_status: str,
    notes: str | None,
) -> None:
    updates = [
        "status = %s",
        "updated_at = NOW()",
        "notes = COALESCE(%s, notes)",
    ]
    params: list[object] = [to_status, notes]
    if to_status == "validated":
        updates.append("validated_at = COALESCE(validated_at, NOW())")
    elif to_status == "active":
        updates.append("activated_at = COALESCE(activated_at, NOW())")
        updates.append("deprecated_at = NULL")
    elif to_status == "deprecated":
        updates.append("deprecated_at = COALESCE(deprecated_at, NOW())")
    elif to_status == "revoked":
        updates.append("revoked_at = COALESCE(revoked_at, NOW())")
    params.append(model_id)
    cur.execute(
        f"""
        UPDATE model_artifacts
        SET {", ".join(updates)}
        WHERE model_id = %s
        """,
        tuple(params),
    )
    if cur.rowcount == 0:
        raise ValueError(f"model artifact does not exist: {model_id}")


def _transition_model_status(
    cur,
    *,
    model_id: str,
    to_status: str,
    action: str,
    actor: str,
    notes: str | None = None,
    details: str | None = None,
) -> None:
    normalized_model_id = _normalize_model_id(model_id)
    from_status = get_model_artifact_status(cur, normalized_model_id, for_update=True)
    if from_status is None:
        raise ValueError(f"model artifact does not exist: {normalized_model_id}")
    validate_model_artifact_transition(from_status, to_status)
    legal_hold = get_model_artifact_legal_hold(cur, normalized_model_id)
    if legal_hold:
        raise ValueError(f"model artifact {normalized_model_id} is on legal hold")
    _set_model_status(cur, model_id=normalized_model_id, to_status=to_status, notes=notes)
    write_model_artifact_audit(
        cur,
        model_id=normalized_model_id,
        from_status=from_status,
        to_status=to_status,
        action=action,
        actor=actor,
        details=details or f"notes={notes}",
    )


def validate_model_artifact(
    cur,
    *,
    model_id: str,
    actor: str,
    notes: str | None,
) -> None:
    _transition_model_status(
        cur,
        model_id=model_id,
        to_status="validated",
        action="validate",
        actor=actor,
        notes=notes,
    )


def activate_model_artifact(
    cur,
    *,
    model_id: str,
    actor: str,
    notes: str | None,
    action: str = "activate",
) -> str | None:
    normalized_model_id = _normalize_model_id(model_id)
    from_status = get_model_artifact_status(cur, normalized_model_id, for_update=True)
    if from_status is None:
        raise ValueError(f"model artifact does not exist: {normalized_model_id}")
    validate_model_artifact_transition(from_status, "active")

    legal_hold = get_model_artifact_legal_hold(cur, normalized_model_id)
    if legal_hold:
        raise ValueError(f"model artifact {normalized_model_id} is on legal hold")

    current_active = get_active_model_id(
        cur,
        exclude_model_id=normalized_model_id,
        for_update=True,
    )
    if current_active is not None:
        current_active_hold = get_model_artifact_legal_hold(cur, current_active)
        if current_active_hold:
            raise ValueError(
                "cannot activate artifact while another active artifact is on legal hold: "
                f"{current_active}"
            )
        _set_model_status(cur, model_id=current_active, to_status="deprecated", notes=notes)
        write_model_artifact_audit(
            cur,
            model_id=current_active,
            from_status="active",
            to_status="deprecated",
            action="deprecate",
            actor=actor,
            details=f"superseded_by={normalized_model_id}",
        )

    _set_model_status(cur, model_id=normalized_model_id, to_status="active", notes=notes)
    write_model_artifact_audit(
        cur,
        model_id=normalized_model_id,
        from_status=from_status,
        to_status="active",
        action=action,
        actor=actor,
        details=f"previous_active={current_active} notes={notes}",
    )
    return current_active


def deprecate_model_artifact(
    cur,
    *,
    model_id: str,
    actor: str,
    notes: str | None,
) -> None:
    _transition_model_status(
        cur,
        model_id=model_id,
        to_status="deprecated",
        action="deprecate",
        actor=actor,
        notes=notes,
    )


def revoke_model_artifact(
    cur,
    *,
    model_id: str,
    actor: str,
    notes: str | None,
) -> None:
    _transition_model_status(
        cur,
        model_id=model_id,
        to_status="revoked",
        action="revoke",
        actor=actor,
        notes=notes,
    )


def _find_rollback_candidate(cur) -> str | None:
    cur.execute(
        """
        SELECT model_id
        FROM model_artifacts
        WHERE status = 'deprecated'
          AND activated_at IS NOT NULL
        ORDER BY activated_at DESC NULLS LAST, updated_at DESC, model_id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        return None
    return str(row[0])


def rollback_model_artifact(
    cur,
    *,
    actor: str,
    to_model_id: str | None,
    notes: str | None,
) -> str:
    target_model_id = _normalize_model_id(to_model_id) if to_model_id is not None else None
    if target_model_id is None:
        target_model_id = _find_rollback_candidate(cur)
        if target_model_id is None:
            raise ValueError("no rollback candidate found")

    activate_model_artifact(
        cur,
        model_id=target_model_id,
        actor=actor,
        notes=notes,
        action="rollback",
    )
    return target_model_id


def list_model_artifacts(cur) -> list[tuple[str, str, str, str, str, str | None]]:
    cur.execute(
        """
        SELECT
          model_id,
          status,
          artifact_uri,
          dataset_ref,
          metrics_ref,
          activated_at::text
        FROM model_artifacts
        ORDER BY created_at DESC, model_id DESC
        """
    )
    return cur.fetchall()


def get_active_model_artifact(cur) -> dict[str, object] | None:
    cur.execute(
        """
        SELECT model_id, status, artifact_uri, sha256, activated_at::text
        FROM model_artifacts
        WHERE status = 'active'
        ORDER BY activated_at DESC NULLS LAST, updated_at DESC, model_id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "model_id": str(row[0]),
        "status": str(row[1]),
        "artifact_uri": str(row[2]),
        "sha256": str(row[3]),
        "activated_at": row[4],
    }


def list_model_artifact_audit(
    cur,
    *,
    model_id: str | None,
    limit: int = 20,
) -> list[tuple[int, str, str | None, str, str, str, str | None, str]]:
    effective_limit = max(1, min(limit, 500))
    if model_id:
        normalized_model_id = _normalize_model_id(model_id)
        cur.execute(
            """
            SELECT id, model_id, from_status, to_status, action, actor, details, created_at::text
            FROM model_artifact_audit
            WHERE model_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (normalized_model_id, effective_limit),
        )
    else:
        cur.execute(
            """
            SELECT id, model_id, from_status, to_status, action, actor, details, created_at::text
            FROM model_artifact_audit
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (effective_limit,),
        )
    return cur.fetchall()


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("SENTINEL_DATABASE_URL or --database-url is required")

    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            try:
                if args.command == "register":
                    register_model_artifact(
                        cur,
                        model_id=args.model_id,
                        artifact_uri=args.artifact_uri,
                        sha256=args.sha256,
                        dataset_ref=args.dataset_ref,
                        metrics_ref=args.metrics_ref,
                        compatibility_json=args.compatibility_json,
                        notes=args.notes,
                        actor=args.actor,
                    )
                    print(f"model artifact registered: {args.model_id}")
                elif args.command == "validate":
                    validate_model_artifact(
                        cur,
                        model_id=args.model_id,
                        actor=args.actor,
                        notes=args.notes,
                    )
                    print(f"model artifact validated: {args.model_id}")
                elif args.command == "activate":
                    previous_active = activate_model_artifact(
                        cur,
                        model_id=args.model_id,
                        actor=args.actor,
                        notes=args.notes,
                    )
                    print(
                        "model artifact activated: "
                        f"{args.model_id} previous_active={previous_active}"
                    )
                elif args.command == "deprecate":
                    deprecate_model_artifact(
                        cur,
                        model_id=args.model_id,
                        actor=args.actor,
                        notes=args.notes,
                    )
                    print(f"model artifact deprecated: {args.model_id}")
                elif args.command == "revoke":
                    revoke_model_artifact(
                        cur,
                        model_id=args.model_id,
                        actor=args.actor,
                        notes=args.notes,
                    )
                    print(f"model artifact revoked: {args.model_id}")
                elif args.command == "rollback":
                    target_model_id = rollback_model_artifact(
                        cur,
                        actor=args.actor,
                        to_model_id=args.to_model_id,
                        notes=args.notes,
                    )
                    print(f"model artifact rollback complete: {target_model_id}")
                elif args.command == "list":
                    rows = list_model_artifacts(cur)
                    for row in rows:
                        print(
                            f"model_id={row[0]} status={row[1]} artifact_uri={row[2]} "
                            f"dataset_ref={row[3]} metrics_ref={row[4]} activated_at={row[5]}"
                        )
                elif args.command == "audit":
                    rows = list_model_artifact_audit(
                        cur,
                        model_id=args.model_id,
                        limit=args.limit,
                    )
                    for row in rows:
                        print(
                            f"id={row[0]} model_id={row[1]} from={row[2]} to={row[3]} "
                            f"action={row[4]} actor={row[5]} details={row[6]} created_at={row[7]}"
                        )
                elif args.command == "active":
                    active = get_active_model_artifact(cur)
                    if args.json:
                        print(json.dumps(active or {}, sort_keys=True))
                    elif active is None:
                        print("no active model artifact")
                    else:
                        print(
                            f"model_id={active['model_id']} status={active['status']} "
                            f"artifact_uri={active['artifact_uri']} "
                            f"sha256={active['sha256']} activated_at={active['activated_at']}"
                        )
            except (InvalidStateTransition, ValueError) as exc:
                raise SystemExit(str(exc)) from exc
        conn.commit()


if __name__ == "__main__":
    main()
