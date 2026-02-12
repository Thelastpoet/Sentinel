from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Literal, cast, get_args

from pydantic import BaseModel, ConfigDict, Field

from sentinel_core.async_state_machine import validate_appeal_transition
from sentinel_core.models import Action, ReasonCode

AppealStatus = Literal[
    "submitted",
    "triaged",
    "in_review",
    "rejected_invalid",
    "resolved_upheld",
    "resolved_reversed",
    "resolved_modified",
]
ResolvedAppealStatus = Literal[
    "resolved_upheld",
    "resolved_reversed",
    "resolved_modified",
]

RESOLVED_APPEAL_STATUSES: set[str] = {
    "resolved_upheld",
    "resolved_reversed",
    "resolved_modified",
}

REVERSED_OR_MODIFIED_STATUSES: set[str] = {
    "resolved_reversed",
    "resolved_modified",
}

KNOWN_APPEAL_STATUSES = set(get_args(AppealStatus))
KNOWN_RESOLVED_APPEAL_STATUSES = set(get_args(ResolvedAppealStatus))
KNOWN_ACTIONS = set(get_args(Action))


class AppealNotFoundError(LookupError):
    pass


class AdminAppealCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_decision_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    original_action: Action
    original_reason_codes: list[ReasonCode] = Field(min_length=1)
    original_model_version: str = Field(min_length=1, max_length=128)
    original_lexicon_version: str = Field(min_length=1, max_length=128)
    original_policy_version: str = Field(min_length=1, max_length=128)
    original_pack_versions: dict[str, str] = Field(min_length=1)
    rationale: str | None = Field(default=None, max_length=2000)


class AdminAppealTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_status: AppealStatus
    rationale: str | None = Field(default=None, max_length=2000)
    resolution_code: str | None = Field(default=None, max_length=128)
    resolution_reason_codes: list[ReasonCode] | None = None


class AdminAppealRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    status: AppealStatus
    request_id: str
    original_decision_id: str
    original_action: Action
    original_reason_codes: list[ReasonCode]
    original_model_version: str
    original_lexicon_version: str
    original_policy_version: str
    original_pack_versions: dict[str, str]
    submitted_by: str
    reviewer_actor: str | None = None
    resolution_code: str | None = None
    resolution_reason_codes: list[ReasonCode] | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class AdminAppealAuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    appeal_id: int = Field(ge=1)
    from_status: AppealStatus | None = None
    to_status: AppealStatus
    actor: str
    rationale: str | None = None
    created_at: datetime


class AdminAppealListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int = Field(ge=0)
    items: list[AdminAppealRecord]


class AdminAppealArtifactVersions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    lexicon: str
    policy: str
    pack: dict[str, str]


class AdminAppealResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ResolvedAppealStatus | None = None
    resolution_code: str | None = None
    resolution_reason_codes: list[ReasonCode] | None = None
    reviewer_actor: str | None = None
    resolved_at: datetime | None = None


class AdminAppealReconstructionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appeal: AdminAppealRecord
    timeline: list[AdminAppealAuditRecord]
    artifact_versions: AdminAppealArtifactVersions
    original_reason_codes: list[ReasonCode]
    resolution: AdminAppealResolution


def _database_url() -> str | None:
    value = os.getenv("SENTINEL_DATABASE_URL", "").strip()
    return value or None


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_reason_codes(value: Any) -> list[str]:
    if value is None:
        return []
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


def _as_resolved_appeal_status(value: Any) -> ResolvedAppealStatus | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized not in KNOWN_RESOLVED_APPEAL_STATUSES:
        return None
    return cast(ResolvedAppealStatus, normalized)


def _as_action(value: Any) -> Action:
    normalized = str(value).strip().upper()
    if normalized not in KNOWN_ACTIONS:
        raise ValueError(f"invalid moderation action: {normalized!r}")
    return cast(Action, normalized)


def _validate_resolution_payload(
    *,
    to_status: str,
    resolution_code: str | None,
    resolution_reason_codes: list[str] | None,
    original_reason_codes: list[str],
) -> tuple[str | None, list[str] | None]:
    if to_status not in RESOLVED_APPEAL_STATUSES:
        if resolution_code is not None or resolution_reason_codes is not None:
            raise ValueError("resolution payload is only allowed for resolved states")
        return None, None

    if not resolution_code or not resolution_code.strip():
        raise ValueError("resolution_code is required for resolved states")

    normalized_resolution = resolution_code.strip()
    normalized_reasons = (
        [str(item) for item in resolution_reason_codes]
        if resolution_reason_codes is not None
        else None
    )

    if to_status in REVERSED_OR_MODIFIED_STATUSES and not normalized_reasons:
        raise ValueError(
            "resolution_reason_codes are required for resolved_reversed/resolved_modified"
        )

    if to_status == "resolved_upheld" and not normalized_reasons:
        normalized_reasons = list(original_reason_codes)

    return normalized_resolution, normalized_reasons


@dataclass
class _InMemoryAppealsStore:
    lock: Lock = field(default_factory=Lock)
    next_appeal_id: int = 1
    next_audit_id: int = 1
    appeals: dict[int, AdminAppealRecord] = field(default_factory=dict)
    timeline: dict[int, list[AdminAppealAuditRecord]] = field(default_factory=dict)

    def reset(self) -> None:
        with self.lock:
            self.next_appeal_id = 1
            self.next_audit_id = 1
            self.appeals.clear()
            self.timeline.clear()

    def create_appeal(
        self,
        payload: AdminAppealCreateRequest,
        *,
        submitted_by: str,
    ) -> AdminAppealRecord:
        created_at = datetime.now(tz=UTC)
        with self.lock:
            appeal_id = self.next_appeal_id
            self.next_appeal_id += 1
            record = AdminAppealRecord(
                id=appeal_id,
                status="submitted",
                request_id=payload.request_id,
                original_decision_id=payload.original_decision_id,
                original_action=payload.original_action,
                original_reason_codes=list(payload.original_reason_codes),
                original_model_version=payload.original_model_version,
                original_lexicon_version=payload.original_lexicon_version,
                original_policy_version=payload.original_policy_version,
                original_pack_versions=dict(payload.original_pack_versions),
                submitted_by=submitted_by,
                created_at=created_at,
                updated_at=created_at,
            )
            self.appeals[appeal_id] = record
            audit = AdminAppealAuditRecord(
                id=self.next_audit_id,
                appeal_id=appeal_id,
                from_status=None,
                to_status="submitted",
                actor=submitted_by,
                rationale=payload.rationale,
                created_at=created_at,
            )
            self.next_audit_id += 1
            self.timeline[appeal_id] = [audit]
            return record

    def list_appeals(
        self,
        *,
        status: str | None,
        request_id: str | None,
        limit: int,
    ) -> AdminAppealListResponse:
        with self.lock:
            filtered = []
            for appeal in self.appeals.values():
                if status is not None and appeal.status != status:
                    continue
                if request_id is not None and appeal.request_id != request_id:
                    continue
                filtered.append(appeal)

            filtered.sort(key=lambda item: (item.created_at, item.id), reverse=True)
            return AdminAppealListResponse(total_count=len(filtered), items=filtered[:limit])

    def transition_appeal(
        self,
        *,
        appeal_id: int,
        payload: AdminAppealTransitionRequest,
        actor: str,
    ) -> AdminAppealRecord:
        now = datetime.now(tz=UTC)
        with self.lock:
            record = self.appeals.get(appeal_id)
            if record is None:
                raise AppealNotFoundError(f"appeal {appeal_id} not found")
            validate_appeal_transition(record.status, payload.to_status)
            resolution_code, resolution_reason_codes = _validate_resolution_payload(
                to_status=payload.to_status,
                resolution_code=payload.resolution_code,
                resolution_reason_codes=payload.resolution_reason_codes,
                original_reason_codes=list(record.original_reason_codes),
            )
            updated = record.model_copy(
                update={
                    "status": payload.to_status,
                    "reviewer_actor": actor,
                    "resolution_code": resolution_code,
                    "resolution_reason_codes": resolution_reason_codes,
                    "updated_at": now,
                    "resolved_at": now if payload.to_status in RESOLVED_APPEAL_STATUSES else None,
                }
            )
            self.appeals[appeal_id] = updated
            audit = AdminAppealAuditRecord(
                id=self.next_audit_id,
                appeal_id=appeal_id,
                from_status=record.status,
                to_status=payload.to_status,
                actor=actor,
                rationale=payload.rationale,
                created_at=now,
            )
            self.next_audit_id += 1
            self.timeline.setdefault(appeal_id, []).append(audit)
            return updated

    def reconstruct(self, *, appeal_id: int) -> AdminAppealReconstructionResponse:
        with self.lock:
            record = self.appeals.get(appeal_id)
            if record is None:
                raise AppealNotFoundError(f"appeal {appeal_id} not found")
            timeline = list(self.timeline.get(appeal_id, []))
            return _build_reconstruction(record, timeline)


@dataclass(frozen=True)
class _PostgresAppealsStore:
    database_url: str

    def _fetch_appeal_record(self, cur, appeal_id: int) -> AdminAppealRecord:
        cur.execute(
            """
            SELECT
              id,
              status,
              request_id,
              original_decision_id,
              original_action,
              original_reason_codes,
              original_model_version,
              original_lexicon_version,
              original_policy_version,
              original_pack_versions,
              submitted_by,
              reviewer_actor,
              resolution_code,
              resolution_reason_codes,
              created_at,
              updated_at,
              resolved_at
            FROM appeals
            WHERE id = %s
            """,
            (appeal_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise AppealNotFoundError(f"appeal {appeal_id} not found")
        return _appeal_from_row(row)

    def create_appeal(
        self,
        payload: AdminAppealCreateRequest,
        *,
        submitted_by: str,
    ) -> AdminAppealRecord:
        psycopg = importlib.import_module("psycopg")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO appeals
                      (
                        status,
                        request_id,
                        original_decision_id,
                        original_action,
                        original_reason_codes,
                        original_model_version,
                        original_lexicon_version,
                        original_policy_version,
                        original_pack_versions,
                        submitted_by
                      )
                    VALUES
                      ('submitted', %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s)
                    RETURNING id
                    """,
                    (
                        payload.request_id,
                        payload.original_decision_id,
                        payload.original_action,
                        json.dumps(payload.original_reason_codes),
                        payload.original_model_version,
                        payload.original_lexicon_version,
                        payload.original_policy_version,
                        json.dumps(payload.original_pack_versions, sort_keys=True),
                        submitted_by,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError("failed to create appeal")
                appeal_id = int(row[0])
                cur.execute(
                    """
                    INSERT INTO appeal_audit
                      (appeal_id, from_status, to_status, actor, rationale)
                    VALUES
                      (%s, %s, 'submitted', %s, %s)
                    """,
                    (appeal_id, None, submitted_by, payload.rationale),
                )
                record = self._fetch_appeal_record(cur, appeal_id)
            conn.commit()
            return record

    def list_appeals(
        self,
        *,
        status: str | None,
        request_id: str | None,
        limit: int,
    ) -> AdminAppealListResponse:
        where_conditions: list[str] = []
        where_params: list[object] = []
        if status is not None:
            where_conditions.append("status = %s")
            where_params.append(status)
        if request_id is not None:
            where_conditions.append("request_id = %s")
            where_params.append(request_id)
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        psycopg = importlib.import_module("psycopg")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(1) FROM appeals {where_clause}",
                    tuple(where_params),
                )
                total_row = cur.fetchone()
                total_count = int(total_row[0]) if total_row is not None else 0
                query_params = list(where_params)
                query_params.append(limit)
                cur.execute(
                    f"""
                    SELECT
                      id,
                      status,
                      request_id,
                      original_decision_id,
                      original_action,
                      original_reason_codes,
                      original_model_version,
                      original_lexicon_version,
                      original_policy_version,
                      original_pack_versions,
                      submitted_by,
                      reviewer_actor,
                      resolution_code,
                      resolution_reason_codes,
                      created_at,
                      updated_at,
                      resolved_at
                    FROM appeals
                    {where_clause}
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    tuple(query_params),
                )
                items = [_appeal_from_row(row) for row in cur.fetchall()]
                return AdminAppealListResponse(total_count=total_count, items=items)

    def transition_appeal(
        self,
        *,
        appeal_id: int,
        payload: AdminAppealTransitionRequest,
        actor: str,
    ) -> AdminAppealRecord:
        psycopg = importlib.import_module("psycopg")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                current = self._fetch_appeal_record(cur, appeal_id)
                validate_appeal_transition(current.status, payload.to_status)
                resolution_code, resolution_reason_codes = _validate_resolution_payload(
                    to_status=payload.to_status,
                    resolution_code=payload.resolution_code,
                    resolution_reason_codes=payload.resolution_reason_codes,
                    original_reason_codes=list(current.original_reason_codes),
                )
                cur.execute(
                    """
                    UPDATE appeals
                    SET status = %s,
                        reviewer_actor = %s,
                        resolution_code = %s,
                        resolution_reason_codes = %s::jsonb,
                        resolved_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        payload.to_status,
                        actor,
                        resolution_code,
                        json.dumps(resolution_reason_codes)
                        if resolution_reason_codes is not None
                        else None,
                        datetime.now(tz=UTC)
                        if payload.to_status in RESOLVED_APPEAL_STATUSES
                        else None,
                        appeal_id,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO appeal_audit
                      (appeal_id, from_status, to_status, actor, rationale)
                    VALUES
                      (%s, %s, %s, %s, %s)
                    """,
                    (
                        appeal_id,
                        current.status,
                        payload.to_status,
                        actor,
                        payload.rationale,
                    ),
                )
                updated = self._fetch_appeal_record(cur, appeal_id)
            conn.commit()
            return updated

    def reconstruct(self, *, appeal_id: int) -> AdminAppealReconstructionResponse:
        psycopg = importlib.import_module("psycopg")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                appeal = self._fetch_appeal_record(cur, appeal_id)
                cur.execute(
                    """
                    SELECT
                      id,
                      appeal_id,
                      from_status,
                      to_status,
                      actor,
                      rationale,
                      created_at
                    FROM appeal_audit
                    WHERE appeal_id = %s
                    ORDER BY created_at ASC, id ASC
                    """,
                    (appeal_id,),
                )
                timeline = [_audit_from_row(row) for row in cur.fetchall()]
            return _build_reconstruction(appeal, timeline)


def _appeal_from_row(row: Any) -> AdminAppealRecord:
    return AdminAppealRecord(
        id=int(row[0]),
        status=_as_appeal_status(row[1]),
        request_id=str(row[2]),
        original_decision_id=str(row[3]),
        original_action=_as_action(row[4]),
        original_reason_codes=_normalize_reason_codes(row[5]),
        original_model_version=str(row[6]),
        original_lexicon_version=str(row[7]),
        original_policy_version=str(row[8]),
        original_pack_versions=_normalize_pack_versions(row[9]),
        submitted_by=str(row[10]),
        reviewer_actor=str(row[11]) if row[11] is not None else None,
        resolution_code=str(row[12]) if row[12] is not None else None,
        resolution_reason_codes=_normalize_reason_codes(row[13]) if row[13] is not None else None,
        created_at=_normalize_timestamp(row[14]),
        updated_at=_normalize_timestamp(row[15]),
        resolved_at=_normalize_timestamp(row[16]) if row[16] is not None else None,
    )


def _audit_from_row(row: Any) -> AdminAppealAuditRecord:
    return AdminAppealAuditRecord(
        id=int(row[0]),
        appeal_id=int(row[1]),
        from_status=_as_appeal_status(row[2]) if row[2] is not None else None,
        to_status=_as_appeal_status(row[3]),
        actor=str(row[4]),
        rationale=str(row[5]) if row[5] is not None else None,
        created_at=_normalize_timestamp(row[6]),
    )


def _build_reconstruction(
    appeal: AdminAppealRecord, timeline: list[AdminAppealAuditRecord]
) -> AdminAppealReconstructionResponse:
    resolution = AdminAppealResolution(
        status=_as_resolved_appeal_status(appeal.status),
        resolution_code=appeal.resolution_code,
        resolution_reason_codes=appeal.resolution_reason_codes,
        reviewer_actor=appeal.reviewer_actor,
        resolved_at=appeal.resolved_at,
    )
    return AdminAppealReconstructionResponse(
        appeal=appeal,
        timeline=timeline,
        artifact_versions=AdminAppealArtifactVersions(
            model=appeal.original_model_version,
            lexicon=appeal.original_lexicon_version,
            policy=appeal.original_policy_version,
            pack=dict(appeal.original_pack_versions),
        ),
        original_reason_codes=list(appeal.original_reason_codes),
        resolution=resolution,
    )


class AppealsRuntime:
    def __init__(self) -> None:
        self._memory_store = _InMemoryAppealsStore()

    def _resolve_store(self):
        database_url = _database_url()
        if database_url:
            return _PostgresAppealsStore(database_url=database_url)
        return self._memory_store

    def create_appeal(
        self,
        payload: AdminAppealCreateRequest,
        *,
        submitted_by: str,
    ) -> AdminAppealRecord:
        store = self._resolve_store()
        return store.create_appeal(payload, submitted_by=submitted_by)

    def list_appeals(
        self,
        *,
        status: AppealStatus | None,
        request_id: str | None,
        limit: int,
    ) -> AdminAppealListResponse:
        store = self._resolve_store()
        return store.list_appeals(status=status, request_id=request_id, limit=limit)

    def transition_appeal(
        self,
        *,
        appeal_id: int,
        payload: AdminAppealTransitionRequest,
        actor: str,
    ) -> AdminAppealRecord:
        store = self._resolve_store()
        return store.transition_appeal(appeal_id=appeal_id, payload=payload, actor=actor)

    def reconstruct(self, *, appeal_id: int) -> AdminAppealReconstructionResponse:
        store = self._resolve_store()
        return store.reconstruct(appeal_id=appeal_id)

    def reset_memory_state(self) -> None:
        self._memory_store.reset()


_APPEALS_RUNTIME = AppealsRuntime()


def get_appeals_runtime() -> AppealsRuntime:
    return _APPEALS_RUNTIME


def reset_appeals_runtime_state() -> None:
    _APPEALS_RUNTIME.reset_memory_state()
