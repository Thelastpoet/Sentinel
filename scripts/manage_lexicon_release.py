from __future__ import annotations

import argparse
import importlib
import json
import os
import re
from pathlib import Path

REASON_CODE_PATTERN = re.compile(r"^R_[A-Z0-9_]+$")
VALID_ACTIONS = {"BLOCK", "REVIEW"}
REQUIRED_INGEST_FIELDS = ("term", "action", "label", "reason_code", "severity", "lang")
SUPPORTED_PROMOTION_PROPOSAL_TYPE = "lexicon"
RETENTION_CLASS_DECISION_RECORD = "decision_record"
RETENTION_CLASS_GOVERNANCE_AUDIT = "governance_audit"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage lexicon release lifecycle (create/activate/deprecate/list)."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("SENTINEL_DATABASE_URL"),
        help="Postgres connection URL. Defaults to SENTINEL_DATABASE_URL.",
    )
    parser.add_argument(
        "--actor",
        default=os.getenv("SENTINEL_RELEASE_ACTOR", os.getenv("USER", "system")),
        help="Actor identifier for audit records.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a draft release.")
    create.add_argument("--version", required=True)
    create.add_argument("--notes", default=None)

    activate = subparsers.add_parser("activate", help="Activate an existing release.")
    activate.add_argument("--version", required=True)

    deprecate = subparsers.add_parser("deprecate", help="Deprecate an existing release.")
    deprecate.add_argument("--version", required=True)

    ingest = subparsers.add_parser("ingest", help="Ingest lexicon entries into a draft release.")
    ingest.add_argument("--version", required=True)
    ingest.add_argument("--input-path", required=True, help="JSON file path.")
    ingest.add_argument(
        "--replace-existing",
        action="store_true",
        help="Deprecate existing active entries in the target release before ingest.",
    )

    validate = subparsers.add_parser(
        "validate", help="Validate release readiness and entry availability."
    )
    validate.add_argument(
        "--version",
        default=None,
        help="Release version to validate. Defaults to the current active release.",
    )

    subparsers.add_parser("list", help="List all releases.")
    audit = subparsers.add_parser("audit", help="List release audit events.")
    audit.add_argument("--version", default=None)
    audit.add_argument("--limit", type=int, default=20)

    promote_proposal = subparsers.add_parser(
        "promote-proposal",
        help=("Promote an approved lexicon proposal into a governed draft release " "artifact."),
    )
    promote_proposal.add_argument("--proposal-id", required=True, type=int)
    promote_proposal.add_argument("--target-version", required=True)
    promote_proposal.add_argument(
        "--notes",
        default=None,
        help="Optional release notes for the created/updated draft release.",
    )
    promote_proposal.add_argument(
        "--rationale",
        default=None,
        help="Optional rationale recorded in proposal review metadata.",
    )

    hold = subparsers.add_parser(
        "hold", help="Apply legal hold on a release version (decision_record class)."
    )
    hold.add_argument("--version", required=True)
    hold.add_argument("--reason", required=True)

    unhold = subparsers.add_parser("unhold", help="Release legal hold on a release version.")
    unhold.add_argument("--version", required=True)
    unhold.add_argument(
        "--reason",
        default=None,
        help="Optional rationale for releasing legal hold.",
    )

    holds = subparsers.add_parser("holds", help="List active legal holds.")
    holds.add_argument("--limit", type=int, default=20)

    return parser.parse_args()


def create_release(cur, version: str, notes: str | None) -> None:
    cur.execute(
        """
        INSERT INTO lexicon_releases
          (version, status, notes, retention_class, legal_hold, created_at, updated_at)
        VALUES
          (%s, 'draft', %s, %s, FALSE, NOW(), NOW())
        ON CONFLICT (version)
        DO UPDATE SET
          notes = COALESCE(EXCLUDED.notes, lexicon_releases.notes),
          retention_class = EXCLUDED.retention_class,
          updated_at = NOW()
        """,
        (version, notes, RETENTION_CLASS_DECISION_RECORD),
    )


def write_audit_event(
    cur,
    *,
    release_version: str,
    action: str,
    actor: str,
    details: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO lexicon_release_audit
          (release_version, action, actor, details, retention_class, legal_hold)
        VALUES
          (%s, %s, %s, %s, %s, FALSE)
        """,
        (release_version, action, actor, details, RETENTION_CLASS_GOVERNANCE_AUDIT),
    )


def write_retention_action_event(
    cur,
    *,
    action: str,
    record_class: str,
    table_name: str,
    actor: str,
    record_count: int,
    details: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO retention_action_audit
          (action, record_class, table_name, actor, record_count, details)
        VALUES
          (%s, %s, %s, %s, %s, %s)
        """,
        (action, record_class, table_name, actor, record_count, details),
    )


def write_release_proposal_audit_event(
    cur,
    *,
    proposal_id: int,
    from_status: str | None,
    to_status: str,
    actor: str,
    details: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO release_proposal_audit
          (proposal_id, from_status, to_status, actor, details, retention_class, legal_hold)
        VALUES
          (%s, %s, %s, %s, %s, %s, FALSE)
        """,
        (
            proposal_id,
            from_status,
            to_status,
            actor,
            details,
            RETENTION_CLASS_GOVERNANCE_AUDIT,
        ),
    )


def get_release_legal_hold(cur, version: str) -> bool | None:
    cur.execute(
        "SELECT legal_hold FROM lexicon_releases WHERE version = %s",
        (version,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return bool(row[0])


def find_active_held_release_to_deprecate(cur, target_version: str) -> str | None:
    cur.execute(
        """
        SELECT version
        FROM lexicon_releases
        WHERE status = 'active'
          AND version <> %s
          AND legal_hold = TRUE
        ORDER BY version ASC
        LIMIT 1
        """,
        (target_version,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return str(row[0])


def count_held_active_entries_for_version(cur, version: str) -> int:
    cur.execute(
        """
        SELECT COUNT(1)
        FROM lexicon_entries
        WHERE lexicon_version = %s
          AND status = 'active'
          AND legal_hold = TRUE
        """,
        (version,),
    )
    row = cur.fetchone()
    if row is None:
        return 0
    return int(row[0])


def apply_release_legal_hold(cur, *, version: str, actor: str, reason: str) -> None:
    cur.execute(
        """
        UPDATE lexicon_releases
        SET legal_hold = TRUE,
            updated_at = NOW()
        WHERE version = %s
        """,
        (version,),
    )
    if cur.rowcount == 0:
        raise ValueError(f"release {version} does not exist")
    cur.execute(
        """
        INSERT INTO legal_holds
          (record_class, table_name, record_key, reason, created_by)
        VALUES
          (%s, 'lexicon_releases', %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (RETENTION_CLASS_DECISION_RECORD, version, reason, actor),
    )
    write_retention_action_event(
        cur,
        action="apply_legal_hold",
        record_class=RETENTION_CLASS_DECISION_RECORD,
        table_name="lexicon_releases",
        actor=actor,
        record_count=1,
        details=f"version={version} reason={reason}",
    )


def release_release_legal_hold(cur, *, version: str, actor: str, reason: str | None = None) -> None:
    cur.execute(
        """
        UPDATE lexicon_releases
        SET legal_hold = FALSE,
            updated_at = NOW()
        WHERE version = %s
        """,
        (version,),
    )
    if cur.rowcount == 0:
        raise ValueError(f"release {version} does not exist")
    cur.execute(
        """
        UPDATE legal_holds
        SET released_at = COALESCE(released_at, NOW()),
            released_by = %s,
            release_reason = %s
        WHERE record_class = %s
          AND table_name = 'lexicon_releases'
          AND record_key = %s
          AND released_at IS NULL
        """,
        (actor, reason, RETENTION_CLASS_DECISION_RECORD, version),
    )
    write_retention_action_event(
        cur,
        action="release_legal_hold",
        record_class=RETENTION_CLASS_DECISION_RECORD,
        table_name="lexicon_releases",
        actor=actor,
        record_count=1,
        details=f"version={version} reason={reason}",
    )


def list_active_legal_holds(
    cur, *, limit: int = 20
) -> list[tuple[int, str, str | None, int | None, str | None, str, str, str]]:
    effective_limit = max(1, min(limit, 500))
    cur.execute(
        """
        SELECT
          id,
          record_class,
          table_name,
          record_id,
          record_key,
          reason,
          created_by,
          created_at::text
        FROM legal_holds
        WHERE released_at IS NULL
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        (effective_limit,),
    )
    return cur.fetchall()


def write_proposal_review_event(
    cur,
    *,
    proposal_id: int,
    action: str,
    actor: str,
    rationale: str | None,
    metadata: dict[str, object] | None = None,
) -> None:
    metadata_payload = json.dumps(metadata or {}, sort_keys=True)
    cur.execute(
        """
        INSERT INTO proposal_reviews
          (proposal_id, action, actor, rationale, metadata, retention_class, legal_hold)
        VALUES
          (%s, %s, %s, %s, %s::jsonb, %s, FALSE)
        """,
        (
            proposal_id,
            action,
            actor,
            rationale,
            metadata_payload,
            RETENTION_CLASS_GOVERNANCE_AUDIT,
        ),
    )


def get_release_proposal(cur, proposal_id: int) -> tuple[int, str, str, str]:
    cur.execute(
        """
        SELECT id, proposal_type, status, title
        FROM release_proposals
        WHERE id = %s
        FOR UPDATE
        """,
        (proposal_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"release proposal {proposal_id} does not exist")
    return int(row[0]), str(row[1]), str(row[2]), str(row[3])


def validate_proposal_transition_for_promotion(current_status: str) -> None:
    try:
        state_machine = importlib.import_module("sentinel_core.async_state_machine")
    except ModuleNotFoundError:
        try:
            state_machine = importlib.import_module("sentinel_api.async_state_machine")
        except ModuleNotFoundError as err:
            status = current_status.strip().lower()
            if status != "approved":
                raise ValueError(f"proposal transition not allowed: {status} -> promoted") from err
            return

    try:
        state_machine.validate_proposal_transition(current_status, "promoted")
    except Exception as exc:  # pragma: no cover - defensive conversion for CLI output
        raise ValueError(str(exc)) from exc


def promote_proposal_to_release(
    cur,
    *,
    proposal_id: int,
    target_version: str,
    actor: str,
    notes: str | None,
    rationale: str | None,
) -> dict[str, object]:
    if proposal_id <= 0:
        raise ValueError("proposal_id must be > 0")

    candidate_version = target_version.strip()
    if not candidate_version:
        raise ValueError("target_version must not be empty")

    proposal_row = get_release_proposal(cur, proposal_id)
    resolved_proposal_id, proposal_type, proposal_status, proposal_title = proposal_row

    if proposal_type != SUPPORTED_PROMOTION_PROPOSAL_TYPE:
        raise ValueError(
            "proposal type is not supported for release promotion: "
            f"{proposal_type} (expected {SUPPORTED_PROMOTION_PROPOSAL_TYPE})"
        )

    validate_proposal_transition_for_promotion(proposal_status)

    existing_release_status = get_release_status(cur, candidate_version)
    if existing_release_status is not None and existing_release_status != "draft":
        raise ValueError(
            "target release version already exists with non-draft status: "
            f"{existing_release_status}"
        )

    release_notes = notes or f"proposal:{resolved_proposal_id} title:{proposal_title}"
    create_release(cur, candidate_version, release_notes)
    write_audit_event(
        cur,
        release_version=candidate_version,
        action="proposal_promote",
        actor=actor,
        details=f"proposal_id={resolved_proposal_id} source_status={proposal_status}",
    )

    cur.execute(
        """
        UPDATE release_proposals
        SET status = 'promoted',
            reviewed_by = %s,
            reviewed_at = COALESCE(reviewed_at, NOW()),
            promoted_at = COALESCE(promoted_at, NOW()),
            updated_at = NOW()
        WHERE id = %s
        """,
        (actor, resolved_proposal_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"release proposal {resolved_proposal_id} does not exist")

    write_release_proposal_audit_event(
        cur,
        proposal_id=resolved_proposal_id,
        from_status=proposal_status,
        to_status="promoted",
        actor=actor,
        details=f"target_release_version={candidate_version}",
    )
    write_proposal_review_event(
        cur,
        proposal_id=resolved_proposal_id,
        action="promote",
        actor=actor,
        rationale=rationale,
        metadata={
            "target_release_version": candidate_version,
            "release_notes": release_notes,
        },
    )

    return {
        "proposal_id": resolved_proposal_id,
        "proposal_status": "promoted",
        "target_release_version": candidate_version,
        "release_status": "draft",
    }


def load_ingest_entries(input_path: str) -> list[dict[str, object]]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        return payload["entries"]
    raise ValueError("ingest input must be a JSON list or an object with an 'entries' list")


def normalize_ingest_entries(raw_entries: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    for index, item in enumerate(raw_entries):
        if not isinstance(item, dict):
            raise ValueError(f"entry {index} must be an object")

        missing = [field for field in REQUIRED_INGEST_FIELDS if field not in item]
        if missing:
            raise ValueError(f"entry {index} missing required fields: {', '.join(missing)}")

        term = str(item["term"]).strip().lower()
        action = str(item["action"]).strip().upper()
        label = str(item["label"]).strip().upper()
        reason_code = str(item["reason_code"]).strip().upper()
        lang = str(item["lang"]).strip().lower()

        raw_severity = item["severity"]
        if isinstance(raw_severity, bool):
            raise ValueError(f"entry {index} has invalid severity")
        try:
            if isinstance(raw_severity, int):
                severity = raw_severity
            elif isinstance(raw_severity, str):
                severity = int(raw_severity.strip())
            else:
                raise ValueError("severity must be int or numeric string")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"entry {index} has invalid severity") from exc

        if not term:
            raise ValueError(f"entry {index} has empty term")
        if action not in VALID_ACTIONS:
            raise ValueError(f"entry {index} has invalid action: {action}")
        if not label:
            raise ValueError(f"entry {index} has empty label")
        if not REASON_CODE_PATTERN.match(reason_code):
            raise ValueError(f"entry {index} has invalid reason_code: {reason_code}")
        if severity < 1 or severity > 3:
            raise ValueError(f"entry {index} severity must be between 1 and 3")
        if not lang or len(lang) > 16:
            raise ValueError(f"entry {index} has invalid lang value")

        key = (term, action, label, reason_code, lang)
        if key in seen:
            raise ValueError(
                f"entry {index} duplicates an earlier entry for term/action/label/reason/lang"
            )
        seen.add(key)

        normalized.append(
            {
                "term": term,
                "action": action,
                "label": label,
                "reason_code": reason_code,
                "severity": severity,
                "lang": lang,
            }
        )

    return normalized


def get_release_status(cur, version: str) -> str | None:
    cur.execute(
        "SELECT status FROM lexicon_releases WHERE version = %s",
        (version,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return str(row[0])


def get_active_release_version(cur) -> str | None:
    cur.execute(
        """
        SELECT version
        FROM lexicon_releases
        WHERE status = 'active'
        ORDER BY activated_at DESC NULLS LAST, updated_at DESC, version DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        return None
    return str(row[0])


def count_active_entries_for_version(cur, version: str) -> int:
    cur.execute(
        """
        SELECT COUNT(1)
        FROM lexicon_entries
        WHERE lexicon_version = %s
          AND status = 'active'
        """,
        (version,),
    )
    row = cur.fetchone()
    if row is None:
        return 0
    return int(row[0])


def activate_release(cur, version: str) -> None:
    status = get_release_status(cur, version)
    if status is None:
        raise ValueError(f"release {version} does not exist")
    release_legal_hold = get_release_legal_hold(cur, version)
    if release_legal_hold:
        raise ValueError(f"release {version} is on legal hold and cannot be activated")
    entry_count = count_active_entries_for_version(cur, version)
    if entry_count == 0:
        raise ValueError(f"release {version} has no active lexicon entries; cannot activate")
    held_active_release = find_active_held_release_to_deprecate(cur, version)
    if held_active_release is not None:
        raise ValueError(
            "cannot activate release while another active release is on legal hold: "
            f"{held_active_release}"
        )

    cur.execute(
        """
        UPDATE lexicon_releases
        SET status = 'deprecated',
            deprecated_at = COALESCE(deprecated_at, NOW()),
            updated_at = NOW()
        WHERE status = 'active'
          AND version <> %s
          AND legal_hold = FALSE
        """,
        (version,),
    )
    cur.execute(
        """
        UPDATE lexicon_releases
        SET status = 'active',
            activated_at = COALESCE(activated_at, NOW()),
            deprecated_at = NULL,
            updated_at = NOW()
        WHERE version = %s
        """,
        (version,),
    )


def deprecate_release(cur, version: str) -> None:
    release_legal_hold = get_release_legal_hold(cur, version)
    if release_legal_hold is None:
        raise ValueError(f"release {version} does not exist")
    if release_legal_hold:
        raise ValueError(f"release {version} is on legal hold and cannot be deprecated")
    cur.execute(
        """
        UPDATE lexicon_releases
        SET status = 'deprecated',
            deprecated_at = COALESCE(deprecated_at, NOW()),
            updated_at = NOW()
        WHERE version = %s
          AND legal_hold = FALSE
        """,
        (version,),
    )
    if cur.rowcount == 0:
        raise ValueError(f"release {version} could not be deprecated")


def list_releases(cur) -> list[tuple[str, str, str | None, str | None]]:
    cur.execute(
        """
        SELECT version, status, activated_at::text, deprecated_at::text
        FROM lexicon_releases
        ORDER BY created_at DESC, version DESC
        """
    )
    return cur.fetchall()


def list_audit_events(
    cur, *, version: str | None = None, limit: int = 20
) -> list[tuple[int, str, str, str, str | None, str]]:
    effective_limit = max(1, min(limit, 500))
    if version:
        cur.execute(
            """
            SELECT id, release_version, action, actor, details, created_at::text
            FROM lexicon_release_audit
            WHERE release_version = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (version, effective_limit),
        )
    else:
        cur.execute(
            """
            SELECT id, release_version, action, actor, details, created_at::text
            FROM lexicon_release_audit
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (effective_limit,),
        )
    return cur.fetchall()


def ingest_entries(
    cur,
    version: str,
    raw_entries: list[dict[str, object]],
    *,
    replace_existing: bool = False,
) -> int:
    status = get_release_status(cur, version)
    if status is None:
        raise ValueError(f"release {version} does not exist")
    if status != "draft":
        raise ValueError(
            "release "
            f"{version} is not draft (status={status}); "
            "ingest allowed only for draft releases"
        )

    entries = normalize_ingest_entries(raw_entries)
    if not entries:
        raise ValueError("ingest payload has no entries")

    if replace_existing:
        held_count = count_held_active_entries_for_version(cur, version)
        if held_count > 0:
            raise ValueError(
                f"release {version} has {held_count} legal-hold active entries; "
                "cannot replace existing entries"
            )
        cur.execute(
            """
            UPDATE lexicon_entries
            SET status = 'deprecated', updated_at = NOW()
            WHERE lexicon_version = %s
              AND status = 'active'
              AND legal_hold = FALSE
            """,
            (version,),
        )

    for item in entries:
        cur.execute(
            """
            INSERT INTO lexicon_entries
              (
                term,
                action,
                label,
                reason_code,
                severity,
                lang,
                status,
                lexicon_version,
                retention_class,
                legal_hold
              )
            VALUES
              (%s, %s, %s, %s, %s, %s, 'active', %s, %s, FALSE)
            ON CONFLICT (term, action, label, reason_code, lang, lexicon_version)
            DO UPDATE SET
              severity = EXCLUDED.severity,
              status = EXCLUDED.status,
              retention_class = EXCLUDED.retention_class,
              updated_at = NOW()
            """,
            (
                item["term"],
                item["action"],
                item["label"],
                item["reason_code"],
                item["severity"],
                item["lang"],
                version,
                RETENTION_CLASS_DECISION_RECORD,
            ),
        )
    return len(entries)


def validate_release(cur, requested_version: str | None) -> dict[str, object]:
    version = requested_version or get_active_release_version(cur)
    if version is None:
        return {
            "ok": False,
            "version": None,
            "status": None,
            "active_entry_count": 0,
            "message": "no active release found and no version provided",
        }

    status = get_release_status(cur, version)
    if status is None:
        return {
            "ok": False,
            "version": version,
            "status": None,
            "active_entry_count": 0,
            "message": "release does not exist",
        }

    entry_count = count_active_entries_for_version(cur, version)
    ok = entry_count > 0
    message = "release is valid for activation" if ok else "release has zero active entries"
    return {
        "ok": ok,
        "version": version,
        "status": status,
        "active_entry_count": entry_count,
        "message": message,
    }


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("SENTINEL_DATABASE_URL or --database-url is required")

    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            if args.command == "create":
                create_release(cur, args.version, args.notes)
                write_audit_event(
                    cur,
                    release_version=args.version,
                    action="create",
                    actor=args.actor,
                    details=f"notes={args.notes}",
                )
                print(f"release created/updated: {args.version}")
            elif args.command == "activate":
                activate_release(cur, args.version)
                write_audit_event(
                    cur,
                    release_version=args.version,
                    action="activate",
                    actor=args.actor,
                    details="status=active",
                )
                print(f"release activated: {args.version}")
            elif args.command == "deprecate":
                deprecate_release(cur, args.version)
                write_audit_event(
                    cur,
                    release_version=args.version,
                    action="deprecate",
                    actor=args.actor,
                    details="status=deprecated",
                )
                print(f"release deprecated: {args.version}")
            elif args.command == "ingest":
                raw_entries = load_ingest_entries(args.input_path)
                count = ingest_entries(
                    cur,
                    args.version,
                    raw_entries,
                    replace_existing=args.replace_existing,
                )
                write_audit_event(
                    cur,
                    release_version=args.version,
                    action="ingest",
                    actor=args.actor,
                    details=f"count={count} replace_existing={args.replace_existing}",
                )
                print(f"ingested {count} entries into release {args.version}")
            elif args.command == "validate":
                report = validate_release(cur, args.version)
                if report["version"] is not None and report["status"] is not None:
                    write_audit_event(
                        cur,
                        release_version=str(report["version"]),
                        action="validate",
                        actor=args.actor,
                        details=(
                            f"ok={report['ok']} status={report['status']} "
                            f"active_entry_count={report['active_entry_count']}"
                        ),
                    )
                print(
                    f"ok={report['ok']} version={report['version']} status={report['status']} "
                    f"active_entry_count={report['active_entry_count']} message={report['message']}"
                )
                if not bool(report["ok"]):
                    raise SystemExit(1)
            elif args.command == "list":
                rows = list_releases(cur)
                for row in rows:
                    print(
                        "version="
                        f"{row[0]} status={row[1]} activated_at={row[2]} "
                        f"deprecated_at={row[3]}"
                    )
            elif args.command == "audit":
                rows = list_audit_events(cur, version=args.version, limit=args.limit)
                for row in rows:
                    print(
                        f"id={row[0]} version={row[1]} action={row[2]} actor={row[3]} "
                        f"details={row[4]} created_at={row[5]}"
                    )
            elif args.command == "promote-proposal":
                report = promote_proposal_to_release(
                    cur,
                    proposal_id=args.proposal_id,
                    target_version=args.target_version,
                    actor=args.actor,
                    notes=args.notes,
                    rationale=args.rationale,
                )
                print(
                    "proposal promoted: "
                    f"proposal_id={report['proposal_id']} "
                    f"proposal_status={report['proposal_status']} "
                    f"target_release_version={report['target_release_version']} "
                    f"release_status={report['release_status']}"
                )
            elif args.command == "hold":
                apply_release_legal_hold(
                    cur,
                    version=args.version,
                    actor=args.actor,
                    reason=args.reason,
                )
                print(f"release legal hold applied: {args.version}")
            elif args.command == "unhold":
                release_release_legal_hold(
                    cur,
                    version=args.version,
                    actor=args.actor,
                    reason=args.reason,
                )
                print(f"release legal hold released: {args.version}")
            elif args.command == "holds":
                rows = list_active_legal_holds(cur, limit=args.limit)
                for row in rows:
                    print(
                        f"id={row[0]} class={row[1]} table={row[2]} record_id={row[3]} "
                        f"record_key={row[4]} reason={row[5]} actor={row[6]} created_at={row[7]}"
                    )
            else:
                raise SystemExit(f"unsupported command: {args.command}")
        conn.commit()


if __name__ == "__main__":
    main()
