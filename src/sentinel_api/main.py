from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from sentinel_api.appeals import (
    AdminAppealCreateRequest,
    AdminAppealListResponse,
    AdminAppealReconstructionResponse,
    AdminAppealRecord,
    AdminAppealTransitionRequest,
    AppealNotFoundError,
    AppealStatus,
    get_appeals_runtime,
)
from sentinel_api.async_priority import async_queue_metrics
from sentinel_api.metrics import metrics
from sentinel_api.oauth import OAuthPrincipal, require_oauth_scope
from sentinel_api.policy import moderate
from sentinel_api.rate_limit import build_rate_limiter
from sentinel_api.transparency import (
    TransparencyAppealsExportResponse,
    TransparencyAppealsReportResponse,
    get_transparency_runtime,
)
from sentinel_core.models import (
    ErrorResponse,
    MetricsResponse,
    ModerationRequest,
    ModerationResponse,
)
from sentinel_core.policy_config import resolve_policy_runtime

logger = logging.getLogger("sentinel.api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Fail fast if electoral phase override is invalid.
    resolve_policy_runtime()
    yield


app = FastAPI(title="Sentinel Moderation API", version="0.1.0", lifespan=lifespan)
rate_limiter = build_rate_limiter()
appeals_runtime = get_appeals_runtime()
transparency_runtime = get_transparency_runtime()


class AdminProposalReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["submit_review", "approve", "reject", "request_changes", "promote"]
    rationale: str | None = Field(default=None, max_length=2000)


class AdminProposalReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: int = Field(ge=1)
    action: Literal["submit_review", "approve", "reject", "request_changes", "promote"]
    actor: str
    status: Literal["accepted"]
    rationale: str | None = None


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    resolved_request_id = response.headers.get("X-Request-ID", request_id)
    response.headers["X-Request-ID"] = resolved_request_id
    metrics.record_http_status(response.status_code)
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": resolved_request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
        )
    )
    return response


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("SENTINEL_API_KEY", "dev-key")
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )


def enforce_rate_limit(response: Response, x_api_key: str | None = Header(default=None)) -> None:
    key = x_api_key or "anonymous"
    decision = rate_limiter.check(key)
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    response.headers["X-RateLimit-Reset"] = str(decision.reset_after_seconds)
    if not decision.allowed:
        retry_after = decision.retry_after_seconds or decision.reset_after_seconds
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(decision.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(decision.reset_after_seconds),
                "Retry-After": str(retry_after),
            },
        )


def _parse_iso_datetime(value: str, *, field_name: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be ISO-8601 datetime",
        ) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", response_model=MetricsResponse)
def get_metrics() -> MetricsResponse:
    snapshot = metrics.snapshot()
    return MetricsResponse(
        action_counts=snapshot["action_counts"],
        http_status_counts=snapshot["http_status_counts"],
        latency_ms_buckets=snapshot["latency_ms_buckets"],
        validation_error_count=snapshot["validation_error_count"],
    )


@app.get("/internal/monitoring/queue/metrics")
def get_internal_queue_metrics(
    principal: OAuthPrincipal = Depends(require_oauth_scope("internal:queue:read")),
) -> dict[str, object]:
    snapshot = async_queue_metrics.snapshot()
    return {
        "queue_depth_by_priority": snapshot["queue_depth_by_priority"],
        "sla_breach_count_by_priority": snapshot["sla_breach_count_by_priority"],
        "actor_client_id": principal.client_id,
    }


@app.get("/admin/release-proposals/permissions")
def get_admin_proposal_permissions(
    principal: OAuthPrincipal = Depends(require_oauth_scope("admin:proposal:read")),
) -> dict[str, object]:
    return {
        "status": "ok",
        "actor_client_id": principal.client_id,
        "scopes": sorted(principal.scopes),
    }


@app.post(
    "/admin/release-proposals/{proposal_id}/review",
    response_model=AdminProposalReviewResponse,
)
def post_admin_proposal_review(
    request: AdminProposalReviewRequest,
    proposal_id: int = Path(ge=1),
    principal: OAuthPrincipal = Depends(require_oauth_scope("admin:proposal:review")),
) -> AdminProposalReviewResponse:
    return AdminProposalReviewResponse(
        proposal_id=proposal_id,
        action=request.action,
        actor=principal.client_id,
        status="accepted",
        rationale=request.rationale,
    )


@app.post("/admin/appeals", response_model=AdminAppealRecord)
def post_admin_appeal(
    request: AdminAppealCreateRequest,
    principal: OAuthPrincipal = Depends(require_oauth_scope("admin:appeal:write")),
) -> AdminAppealRecord:
    try:
        record = appeals_runtime.create_appeal(request, submitted_by=principal.client_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    logger.info(
        json.dumps(
            {
                "event": "appeal_created",
                "appeal_id": record.id,
                "status": record.status,
                "request_id": record.request_id,
                "actor_client_id": principal.client_id,
            }
        )
    )
    return record


@app.get("/admin/appeals", response_model=AdminAppealListResponse)
def list_admin_appeals(
    status_filter: AppealStatus | None = Query(default=None, alias="status"),
    request_id: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
    principal: OAuthPrincipal = Depends(require_oauth_scope("admin:appeal:read")),
) -> AdminAppealListResponse:
    response = appeals_runtime.list_appeals(
        status=status_filter,
        request_id=request_id,
        limit=limit,
    )
    logger.info(
        json.dumps(
            {
                "event": "appeal_list",
                "actor_client_id": principal.client_id,
                "status_filter": status_filter,
                "request_id_filter": request_id,
                "count": len(response.items),
            }
        )
    )
    return response


@app.post("/admin/appeals/{appeal_id}/transition", response_model=AdminAppealRecord)
def post_admin_appeal_transition(
    request: AdminAppealTransitionRequest,
    appeal_id: int = Path(ge=1),
    principal: OAuthPrincipal = Depends(require_oauth_scope("admin:appeal:write")),
) -> AdminAppealRecord:
    try:
        record = appeals_runtime.transition_appeal(
            appeal_id=appeal_id,
            payload=request,
            actor=principal.client_id,
        )
    except AppealNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    logger.info(
        json.dumps(
            {
                "event": "appeal_transition",
                "appeal_id": appeal_id,
                "to_status": request.to_status,
                "actor_client_id": principal.client_id,
            }
        )
    )
    return record


@app.get(
    "/admin/appeals/{appeal_id}/reconstruct",
    response_model=AdminAppealReconstructionResponse,
)
def get_admin_appeal_reconstruction(
    appeal_id: int = Path(ge=1),
    principal: OAuthPrincipal = Depends(require_oauth_scope("admin:appeal:read")),
) -> AdminAppealReconstructionResponse:
    try:
        reconstruction = appeals_runtime.reconstruct(appeal_id=appeal_id)
    except AppealNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    logger.info(
        json.dumps(
            {
                "event": "appeal_reconstruct",
                "appeal_id": appeal_id,
                "actor_client_id": principal.client_id,
            }
        )
    )
    return reconstruction


@app.get(
    "/admin/transparency/reports/appeals",
    response_model=TransparencyAppealsReportResponse,
)
def get_transparency_appeals_report(
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    principal: OAuthPrincipal = Depends(require_oauth_scope("admin:transparency:read")),
) -> TransparencyAppealsReportResponse:
    created_from_dt = None
    created_to_dt = None
    if created_from is not None:
        created_from_dt = _parse_iso_datetime(created_from, field_name="created_from")
    if created_to is not None:
        created_to_dt = _parse_iso_datetime(created_to, field_name="created_to")
    report = transparency_runtime.build_appeals_report(
        created_from=created_from_dt,
        created_to=created_to_dt,
    )
    logger.info(
        json.dumps(
            {
                "event": "transparency_report_generated",
                "actor_client_id": principal.client_id,
                "created_from": created_from,
                "created_to": created_to,
                "total_appeals": report.total_appeals,
            }
        )
    )
    return report


@app.get(
    "/admin/transparency/exports/appeals",
    response_model=TransparencyAppealsExportResponse,
)
def get_transparency_appeals_export(
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    include_identifiers: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=5000),
    principal: OAuthPrincipal = Depends(require_oauth_scope("admin:transparency:export")),
) -> TransparencyAppealsExportResponse:
    if include_identifiers and "admin:transparency:identifiers" not in principal.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing OAuth scope: admin:transparency:identifiers",
        )

    created_from_dt = None
    created_to_dt = None
    if created_from is not None:
        created_from_dt = _parse_iso_datetime(created_from, field_name="created_from")
    if created_to is not None:
        created_to_dt = _parse_iso_datetime(created_to, field_name="created_to")
    export_payload = transparency_runtime.export_appeals_records(
        created_from=created_from_dt,
        created_to=created_to_dt,
        limit=limit,
        include_identifiers=include_identifiers,
    )
    logger.info(
        json.dumps(
            {
                "event": "transparency_export_generated",
                "actor_client_id": principal.client_id,
                "include_identifiers": include_identifiers,
                "limit": limit,
                "record_count": export_payload.total_count,
            }
        )
    )
    return export_payload


@app.post(
    "/v1/moderate",
    response_model=ModerationResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def moderate_text(
    http_request: Request,
    response: Response,
    request: ModerationRequest,
    _: None = Depends(require_api_key),
    __: None = Depends(enforce_rate_limit),
) -> ModerationResponse:
    effective_request_id = request.request_id or http_request.state.request_id
    runtime = resolve_policy_runtime()
    result = moderate(request.text, runtime=runtime)
    effective_phase = runtime.effective_phase.value if runtime.effective_phase is not None else None
    effective_deployment_stage = runtime.effective_deployment_stage.value
    response.headers["X-Request-ID"] = effective_request_id
    metrics.record_action(result.action)
    metrics.record_moderation_latency(result.latency_ms)
    logger.info(
        json.dumps(
            {
                "event": "moderation_decision",
                "request_id": effective_request_id,
                "action": result.action,
                "labels": result.labels,
                "reason_codes": result.reason_codes,
                "latency_ms": result.latency_ms,
                "model_version": result.model_version,
                "lexicon_version": result.lexicon_version,
                "policy_version": result.policy_version,
                "effective_phase": effective_phase,
                "effective_deployment_stage": effective_deployment_stage,
            }
        )
    )
    return result


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[no-untyped-def]
    request_id = getattr(request.state, "request_id", str(uuid4()))
    payload = ErrorResponse(
        error_code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        request_id=request_id,
    )
    from fastapi.responses import JSONResponse

    headers: dict[str, str] = {"X-Request-ID": request_id}
    if exc.headers:
        for key, value in exc.headers.items():
            headers[key] = value

    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content=payload.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):  # type: ignore[no-untyped-def]
    error_count = len(exc.errors())
    request_id = getattr(request.state, "request_id", str(uuid4()))
    metrics.record_validation_error()
    payload = ErrorResponse(
        error_code="HTTP_400",
        message=f"Invalid request payload ({error_count} validation error(s))",
        request_id=request_id,
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        headers={"X-Request-ID": request_id},
        content=payload.model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):  # type: ignore[no-untyped-def]
    request_id = getattr(request.state, "request_id", str(uuid4()))
    logger.exception(
        "unhandled_exception",
        extra={"request_id": request_id, "path": request.url.path},
    )
    payload = ErrorResponse(
        error_code="HTTP_500",
        message="Internal server error",
        request_id=request_id,
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={"X-Request-ID": request_id},
        content=payload.model_dump(),
    )
