from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast, get_args

from pydantic import BaseModel, ConfigDict, Field

from sentinel_api.appeals import (
    AppealStatus,
    ResolvedAppealStatus,
    get_appeals_runtime,
)
from sentinel_core.models import Action, ReasonCode

RESOLVED_STATUSES: set[str] = {
    "resolved_upheld",
    "resolved_reversed",
    "resolved_modified",
}
OPEN_STATUSES: set[str] = {"submitted", "triaged", "in_review"}
DEFAULT_MEMORY_SCAN_LIMIT = 50000
KNOWN_APPEAL_STATUSES = set(get_args(AppealStatus))
KNOWN_RESOLVED_STATUSES = set(get_args(ResolvedAppealStatus))
KNOWN_ACTIONS = set(get_args(Action))


class TransparencyExportArtifactVersions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    lexicon: str
    policy: str
    pack: dict[str, str]


class TransparencyExportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appeal_id: int = Field(ge=1)
    status: AppealStatus
    original_action: Action
    original_reason_codes: list[ReasonCode]
    resolution_status: ResolvedAppealStatus | None = None
    resolution_code: str | None = None
    resolution_reason_codes: list[ReasonCode] | None = None
    artifact_versions: TransparencyExportArtifactVersions
    request_id: str | None = None
    original_decision_id: str | None = None
    transition_count: int = Field(ge=0)
    created_at: datetime
    resolved_at: datetime | None = None


class TransparencyAppealsExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    include_identifiers: bool
    total_count: int = Field(ge=0)
    records: list[TransparencyExportRecord]


class TransparencyAppealsReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    total_appeals: int = Field(ge=0)
    open_appeals: int = Field(ge=0)
    resolved_appeals: int = Field(ge=0)
    backlog_over_72h: int = Field(ge=0)
    reversal_rate: float = Field(ge=0, le=1)
    mean_resolution_hours: float | None = Field(default=None, ge=0)
    status_counts: dict[str, int]
    resolution_counts: dict[str, int]


@dataclass(frozen=True)
class _AppealExportCandidate:
    appeal_id: int
    status: AppealStatus
    request_id: str
    original_decision_id: str
    original_action: Action
    original_reason_codes: list[str]
    original_model_version: str
    original_lexicon_version: str
    original_policy_version: str
    original_pack_versions: dict[str, str]
    resolution_code: str | None
    resolution_reason_codes: list[str] | None
    created_at: datetime
    resolved_at: datetime | None
    transition_count: int


def _database_url() -> str | None:
    value = os.getenv("SENTINEL_DATABASE_URL", "").strip()
    return value or None


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_reason_codes(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _normalize_pack_versions(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _as_appeal_status(value: Any) -> AppealStatus:
    normalized = str(value).strip()
    if normalized not in KNOWN_APPEAL_STATUSES:
        raise ValueError(f"invalid appeal status: {normalized!r}")
    return cast(AppealStatus, normalized)


def _as_resolved_status(value: Any) -> ResolvedAppealStatus | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized not in KNOWN_RESOLVED_STATUSES:
        return None
    return cast(ResolvedAppealStatus, normalized)


def _as_action(value: Any) -> Action:
    normalized = str(value).strip().upper()
    if normalized not in KNOWN_ACTIONS:
        raise ValueError(f"invalid moderation action: {normalized!r}")
    return cast(Action, normalized)


def _candidate_from_row(row: Any) -> _AppealExportCandidate:
    return _AppealExportCandidate(
        appeal_id=int(row[0]),
        status=_as_appeal_status(row[1]),
        request_id=str(row[2]),
        original_decision_id=str(row[3]),
        original_action=_as_action(row[4]),
        original_reason_codes=_normalize_reason_codes(row[5]),
        original_model_version=str(row[6]),
        original_lexicon_version=str(row[7]),
        original_policy_version=str(row[8]),
        original_pack_versions=_normalize_pack_versions(row[9]),
        resolution_code=str(row[10]) if row[10] is not None else None,
        resolution_reason_codes=_normalize_reason_codes(row[11]) if row[11] is not None else None,
        created_at=_normalize_timestamp(row[12]),
        resolved_at=_normalize_timestamp(row[13]) if row[13] is not None else None,
        transition_count=int(row[14]),
    )


def _build_where_clause(
    *,
    created_from: datetime | None,
    created_to: datetime | None,
) -> tuple[str, list[object]]:
    filters: list[str] = []
    params: list[object] = []
    if created_from is not None:
        filters.append("a.created_at >= %s")
        params.append(_normalize_timestamp(created_from))
    if created_to is not None:
        filters.append("a.created_at <= %s")
        params.append(_normalize_timestamp(created_to))
    if not filters:
        return "", params
    return "WHERE " + " AND ".join(filters), params


def _fetch_candidates_postgres(
    *,
    database_url: str,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int | None,
) -> list[_AppealExportCandidate]:
    where_clause, params = _build_where_clause(
        created_from=created_from,
        created_to=created_to,
    )
    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT %s"
        params.append(limit)
    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                  a.id,
                  a.status,
                  a.request_id,
                  a.original_decision_id,
                  a.original_action,
                  a.original_reason_codes,
                  a.original_model_version,
                  a.original_lexicon_version,
                  a.original_policy_version,
                  a.original_pack_versions,
                  a.resolution_code,
                  a.resolution_reason_codes,
                  a.created_at,
                  a.resolved_at,
                  COALESCE(aa.transition_count, 0)
                FROM appeals AS a
                LEFT JOIN (
                  SELECT appeal_id, COUNT(1)::bigint AS transition_count
                  FROM appeal_audit
                  GROUP BY appeal_id
                ) AS aa
                  ON aa.appeal_id = a.id
                {where_clause}
                ORDER BY a.created_at DESC, a.id DESC
                {limit_clause}
                """,
                tuple(params),
            )
            return [_candidate_from_row(row) for row in cur.fetchall()]


def _fetch_candidates_memory(
    *,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int | None,
) -> list[_AppealExportCandidate]:
    runtime = get_appeals_runtime()
    listed = runtime.list_appeals(
        status=None,
        request_id=None,
        limit=DEFAULT_MEMORY_SCAN_LIMIT,
    )
    candidates: list[_AppealExportCandidate] = []
    for appeal in listed.items:
        created_at = _normalize_timestamp(appeal.created_at)
        if created_from is not None and created_at < _normalize_timestamp(created_from):
            continue
        if created_to is not None and created_at > _normalize_timestamp(created_to):
            continue
        reconstruction = runtime.reconstruct(appeal_id=appeal.id)
        candidates.append(
            _AppealExportCandidate(
                appeal_id=appeal.id,
                status=appeal.status,
                request_id=appeal.request_id,
                original_decision_id=appeal.original_decision_id,
                original_action=appeal.original_action,
                original_reason_codes=list(appeal.original_reason_codes),
                original_model_version=appeal.original_model_version,
                original_lexicon_version=appeal.original_lexicon_version,
                original_policy_version=appeal.original_policy_version,
                original_pack_versions=dict(appeal.original_pack_versions),
                resolution_code=appeal.resolution_code,
                resolution_reason_codes=appeal.resolution_reason_codes,
                created_at=created_at,
                resolved_at=appeal.resolved_at,
                transition_count=len(reconstruction.timeline),
            )
        )
    candidates.sort(key=lambda row: (row.created_at, row.appeal_id), reverse=True)
    if limit is None:
        return candidates
    return candidates[:limit]


def _fetch_candidates(
    *,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int | None,
) -> list[_AppealExportCandidate]:
    database_url = _database_url()
    if database_url:
        return _fetch_candidates_postgres(
            database_url=database_url,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
    return _fetch_candidates_memory(
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )


def _to_export_record(
    candidate: _AppealExportCandidate, *, include_identifiers: bool
) -> TransparencyExportRecord:
    resolution_status = _as_resolved_status(candidate.status)
    return TransparencyExportRecord(
        appeal_id=candidate.appeal_id,
        status=candidate.status,
        original_action=candidate.original_action,
        original_reason_codes=list(candidate.original_reason_codes),
        resolution_status=resolution_status,
        resolution_code=candidate.resolution_code,
        resolution_reason_codes=candidate.resolution_reason_codes,
        artifact_versions=TransparencyExportArtifactVersions(
            model=candidate.original_model_version,
            lexicon=candidate.original_lexicon_version,
            policy=candidate.original_policy_version,
            pack=dict(candidate.original_pack_versions),
        ),
        request_id=candidate.request_id if include_identifiers else None,
        original_decision_id=candidate.original_decision_id if include_identifiers else None,
        transition_count=candidate.transition_count,
        created_at=candidate.created_at,
        resolved_at=candidate.resolved_at,
    )


class TransparencyRuntime:
    def build_appeals_report(
        self,
        *,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> TransparencyAppealsReportResponse:
        candidates = _fetch_candidates(
            created_from=created_from,
            created_to=created_to,
            limit=None,
        )
        statuses = sorted(OPEN_STATUSES | RESOLVED_STATUSES | {"rejected_invalid"})
        status_counts: dict[str, int] = {status: 0 for status in statuses}
        resolution_counts: dict[str, int] = {
            "resolved_upheld": 0,
            "resolved_reversed": 0,
            "resolved_modified": 0,
        }
        resolution_hours: list[float] = []
        backlog_over_72h = 0
        now = datetime.now(tz=UTC)
        for candidate in candidates:
            status_counts[candidate.status] = status_counts.get(candidate.status, 0) + 1
            if candidate.status in RESOLVED_STATUSES:
                resolution_counts[candidate.status] += 1
            if candidate.resolved_at is not None:
                elapsed = candidate.resolved_at - candidate.created_at
                resolution_hours.append(max(0.0, elapsed.total_seconds() / 3600.0))
            elif candidate.status in OPEN_STATUSES and now - candidate.created_at >= timedelta(
                hours=72
            ):
                backlog_over_72h += 1
        total_appeals = len(candidates)
        resolved_appeals = sum(resolution_counts.values())
        open_appeals = sum(status_counts.get(status, 0) for status in OPEN_STATUSES)
        reversal_rate = (
            resolution_counts["resolved_reversed"] / resolved_appeals
            if resolved_appeals > 0
            else 0.0
        )
        mean_resolution_hours = (
            sum(resolution_hours) / len(resolution_hours) if resolution_hours else None
        )
        return TransparencyAppealsReportResponse(
            generated_at=datetime.now(tz=UTC),
            total_appeals=total_appeals,
            open_appeals=open_appeals,
            resolved_appeals=resolved_appeals,
            backlog_over_72h=backlog_over_72h,
            reversal_rate=round(reversal_rate, 6),
            mean_resolution_hours=round(mean_resolution_hours, 3)
            if mean_resolution_hours is not None
            else None,
            status_counts=status_counts,
            resolution_counts=resolution_counts,
        )

    def export_appeals_records(
        self,
        *,
        created_from: datetime | None,
        created_to: datetime | None,
        limit: int,
        include_identifiers: bool,
    ) -> TransparencyAppealsExportResponse:
        candidates = _fetch_candidates(
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
        records = [
            _to_export_record(candidate, include_identifiers=include_identifiers)
            for candidate in candidates
        ]
        return TransparencyAppealsExportResponse(
            generated_at=datetime.now(tz=UTC),
            include_identifiers=include_identifiers,
            total_count=len(records),
            records=records,
        )


_TRANSPARENCY_RUNTIME = TransparencyRuntime()


def get_transparency_runtime() -> TransparencyRuntime:
    return _TRANSPARENCY_RUNTIME
