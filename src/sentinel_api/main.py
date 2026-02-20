from __future__ import annotations

import json
import os
import re
import secrets
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path as FilePath
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
from fastapi.responses import JSONResponse, PlainTextResponse
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
from sentinel_api.db_pool import close_pool, get_pool
from sentinel_api.logging import get_logger
from sentinel_api.metrics import metrics
from sentinel_api.model_artifact_repository import resolve_runtime_model_version
from sentinel_api.model_registry import predict_classifier_shadow
from sentinel_api.oauth import OAuthPrincipal, require_oauth_scope
from sentinel_api.policy import moderate
from sentinel_api.rate_limit import build_rate_limiter
from sentinel_api.result_cache import get_cached_result, make_cache_key, set_cached_result
from sentinel_api.transparency import (
    TransparencyAppealsExportResponse,
    TransparencyAppealsReportResponse,
    get_transparency_runtime,
)
from sentinel_core.models import (
    Action,
    ErrorResponse,
    MetricsResponse,
    ModerationBatchItemResult,
    ModerationBatchRequest,
    ModerationBatchResponse,
    ModerationRequest,
    ModerationResponse,
    PublicAppealCreateRequest,
    PublicAppealCreateResponse,
)
from sentinel_core.policy_config import DeploymentStage, resolve_policy_runtime
from sentinel_langpack.registry import resolve_pack_versions
from sentinel_lexicon.lexicon import get_lexicon_matcher

logger = get_logger("sentinel.api")
CLASSIFIER_SHADOW_ENABLED_ENV = "SENTINEL_CLASSIFIER_SHADOW_ENABLED"
SHADOW_PREDICTIONS_PATH_ENV = "SENTINEL_SHADOW_PREDICTIONS_PATH"
RESULT_CACHE_ENABLED_ENV = "SENTINEL_RESULT_CACHE_ENABLED"
RESULT_CACHE_TTL_SECONDS_ENV = "SENTINEL_RESULT_CACHE_TTL_SECONDS"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _coerce_request_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 128:
        return None
    if not _REQUEST_ID_RE.match(normalized):
        return None
    return normalized


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Fail fast if electoral phase override is invalid.
    resolve_policy_runtime()
    database_url = os.getenv("SENTINEL_DATABASE_URL", "").strip()
    if database_url:
        get_pool(database_url)
    try:
        yield
    finally:
        close_pool()


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
    request_id = _coerce_request_id(request.headers.get("X-Request-ID")) or str(uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    resolved_request_id = _coerce_request_id(response.headers.get("X-Request-ID")) or request_id
    response.headers["X-Request-ID"] = resolved_request_id
    metrics.record_http_status(response.status_code)
    logger.info(
        "http_request",
        request_id=resolved_request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("SENTINEL_API_KEY")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )


def enforce_rate_limit(response: Response, x_api_key: str | None = Header(default=None)) -> None:
    _enforce_rate_limit_cost(response, x_api_key=x_api_key, cost=1)


def _enforce_rate_limit_cost(response: Response, *, x_api_key: str | None, cost: int) -> None:
    key = x_api_key or "anonymous"
    decision = rate_limiter.check(key, cost=cost)
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


def _is_truthy_env(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _shadow_classifier_enabled(*, deployment_stage: DeploymentStage) -> bool:
    if not _is_truthy_env(CLASSIFIER_SHADOW_ENABLED_ENV):
        return False
    return deployment_stage in {DeploymentStage.SHADOW, DeploymentStage.ADVISORY}


def _predicted_action_from_labels(labels: Sequence[str]) -> Action:
    if labels:
        return "REVIEW"
    return "ALLOW"


def _persist_shadow_prediction(record: dict[str, object]) -> None:
    path_value = os.getenv(SHADOW_PREDICTIONS_PATH_ENV, "").strip()
    if not path_value:
        return
    path = FilePath(path_value)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")
    except OSError as exc:
        logger.warning(
            "classifier_shadow_persist_error",
            path=str(path),
            error=str(exc),
        )


def _record_classifier_shadow_prediction(
    *,
    request_id: str,
    text: str,
    result: ModerationResponse,
    deployment_stage: DeploymentStage,
) -> None:
    if not _shadow_classifier_enabled(deployment_stage=deployment_stage):
        return

    shadow_result = predict_classifier_shadow(text)
    predicted_labels = [label for label, _ in shadow_result.predicted_labels]
    predicted_action = _predicted_action_from_labels(predicted_labels)
    disagreement = predicted_action != result.action or set(predicted_labels) != set(result.labels)
    metrics.record_classifier_shadow(
        provider_id=shadow_result.provider_id,
        status=shadow_result.status,
        latency_ms=shadow_result.latency_ms,
        disagreed=disagreement,
    )
    predictions = [
        {"label": label, "score": score} for label, score in shadow_result.predicted_labels
    ]
    record = {
        "request_id": request_id,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "classifier_provider_id": shadow_result.provider_id,
        "classifier_model_version": shadow_result.model_version,
        "classifier_status": shadow_result.status,
        "classifier_latency_ms": shadow_result.latency_ms,
        "predictions": predictions,
        "predicted_action": predicted_action,
        "enforced_action": result.action,
        "enforced_labels": result.labels,
        "policy_version": result.policy_version,
        "effective_deployment_stage": deployment_stage.value,
        "disagreement": disagreement,
    }
    logger.info("classifier_shadow_prediction", **record)
    _persist_shadow_prediction(record)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


def _check_lexicon_ready() -> str:
    try:
        matcher = get_lexicon_matcher()
    except Exception:
        return "error"
    if matcher.entries:
        return "ok"
    return "empty"


def _check_db_ready(database_url: str) -> str:
    normalized = database_url.strip()
    if not normalized:
        return "empty"
    try:
        from sentinel_api.db_pool import get_pool

        pool = get_pool(normalized)
        if pool is not None:
            conn_ctx = pool.connection()
        else:
            import psycopg

            conn_ctx = psycopg.connect(normalized)
        with conn_ctx as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception:
        return "error"
    return "ok"


def _check_redis_ready(redis_url: str) -> str:
    normalized = redis_url.strip()
    if not normalized:
        return "empty"
    try:
        import redis

        client = redis.Redis.from_url(
            normalized,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            health_check_interval=10,
        )
        client.ping()
    except Exception:
        return "error"
    return "ok"


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    checks: dict[str, str] = {}
    checks["lexicon"] = _check_lexicon_ready()

    database_url = os.getenv("SENTINEL_DATABASE_URL", "")
    if database_url.strip():
        checks["db"] = _check_db_ready(database_url)

    redis_url = os.getenv("SENTINEL_REDIS_URL", "")
    if redis_url.strip():
        checks["redis"] = _check_redis_ready(redis_url)

    degraded = any(value == "error" for value in checks.values())
    status_value = "degraded" if degraded else "ready"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE if degraded else status.HTTP_200_OK
    return JSONResponse(
        status_code=http_status,
        content={"status": status_value, "checks": checks},
    )


@app.get("/metrics", response_model=MetricsResponse)
def get_metrics() -> MetricsResponse:
    snapshot = metrics.snapshot()
    return MetricsResponse(
        action_counts=snapshot["action_counts"],
        http_status_counts=snapshot["http_status_counts"],
        latency_ms_buckets=snapshot["latency_ms_buckets"],
        validation_error_count=snapshot["validation_error_count"],
    )


@app.get("/metrics/prometheus")
def get_metrics_prometheus() -> PlainTextResponse:
    return PlainTextResponse(content=metrics.prometheus_text())


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
        "appeal_created",
        appeal_id=record.id,
        status=record.status,
        request_id=record.request_id,
        actor_client_id=principal.client_id,
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
        "appeal_list",
        actor_client_id=principal.client_id,
        status_filter=status_filter,
        request_id_filter=request_id,
        count=len(response.items),
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
        "appeal_transition",
        appeal_id=appeal_id,
        to_status=request.to_status,
        actor_client_id=principal.client_id,
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
        "appeal_reconstruct",
        appeal_id=appeal_id,
        actor_client_id=principal.client_id,
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
        "transparency_report_generated",
        actor_client_id=principal.client_id,
        created_from=created_from,
        created_to=created_to,
        total_appeals=report.total_appeals,
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
        "transparency_export_generated",
        actor_client_id=principal.client_id,
        include_identifiers=include_identifiers,
        limit=limit,
        record_count=export_payload.total_count,
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
    if request.request_id is not None and _coerce_request_id(request.request_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request_id contains invalid characters",
        )
    effective_request_id = request.request_id or http_request.state.request_id
    runtime = resolve_policy_runtime()
    response.headers["X-Request-ID"] = effective_request_id

    cache_enabled = _is_truthy_env(RESULT_CACHE_ENABLED_ENV)
    redis_url = os.getenv("SENTINEL_REDIS_URL", "").strip()
    cache_key: str | None = None
    if cache_enabled and redis_url:
        matcher = get_lexicon_matcher()
        cache_key = make_cache_key(
            request.text,
            policy_version=runtime.effective_policy_version,
            lexicon_version=matcher.version,
            model_version=resolve_runtime_model_version(runtime.config.model_version),
            pack_versions=resolve_pack_versions(runtime.config.pack_versions),
            deployment_stage=runtime.effective_deployment_stage.value,
            context=request.context,
        )
        cached = get_cached_result(cache_key, redis_url)
        if cached is not None:
            response.headers["X-Cache"] = "HIT"
            metrics.record_action(cached.action)
            metrics.record_moderation_latency(cached.latency_ms)
            return cached
        response.headers["X-Cache"] = "MISS"

    result = moderate(request.text, context=request.context, runtime=runtime)
    effective_phase = runtime.effective_phase.value if runtime.effective_phase is not None else None
    effective_deployment_stage = runtime.effective_deployment_stage.value
    metrics.record_action(result.action)
    metrics.record_moderation_latency(result.latency_ms)
    if cache_key is not None and redis_url:
        ttl_raw = os.getenv(RESULT_CACHE_TTL_SECONDS_ENV, "60").strip()
        try:
            ttl = int(ttl_raw)
        except ValueError:
            ttl = 60
        set_cached_result(cache_key, result, redis_url, ttl=ttl)
    _record_classifier_shadow_prediction(
        request_id=effective_request_id,
        text=request.text,
        result=result,
        deployment_stage=runtime.effective_deployment_stage,
    )
    logger.info(
        "moderation_decision",
        request_id=effective_request_id,
        action=result.action,
        labels=result.labels,
        reason_codes=result.reason_codes,
        latency_ms=result.latency_ms,
        model_version=result.model_version,
        lexicon_version=result.lexicon_version,
        policy_version=result.policy_version,
        effective_phase=effective_phase,
        effective_deployment_stage=effective_deployment_stage,
    )
    return result


@app.post(
    "/v1/moderate/batch",
    response_model=ModerationBatchResponse,
    responses={
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def moderate_batch(
    http_request: Request,
    response: Response,
    request: ModerationBatchRequest,
    _: None = Depends(require_api_key),
    x_api_key: str | None = Header(default=None),
) -> ModerationBatchResponse:
    effective_request_id = http_request.state.request_id
    response.headers["X-Request-ID"] = effective_request_id

    _enforce_rate_limit_cost(response, x_api_key=x_api_key, cost=len(request.items))

    runtime = resolve_policy_runtime()
    items: list[ModerationBatchItemResult] = []
    succeeded = 0
    failed = 0

    for item in request.items:
        item_request_id = item.request_id or str(uuid4())
        if _coerce_request_id(item_request_id) is None:
            failed += 1
            items.append(
                ModerationBatchItemResult(
                    request_id=item_request_id,
                    result=None,
                    error=ErrorResponse(
                        error_code="HTTP_400",
                        message="request_id contains invalid characters",
                        request_id=item_request_id,
                    ),
                )
            )
            continue

        try:
            result = moderate(item.text, context=item.context, runtime=runtime)
        except Exception:
            failed += 1
            items.append(
                ModerationBatchItemResult(
                    request_id=item_request_id,
                    result=None,
                    error=ErrorResponse(
                        error_code="HTTP_500",
                        message="Internal server error",
                        request_id=item_request_id,
                    ),
                )
            )
            continue

        succeeded += 1
        items.append(
            ModerationBatchItemResult(
                request_id=item_request_id,
                result=result,
                error=None,
            )
        )

    return ModerationBatchResponse(
        items=items,
        total=len(items),
        succeeded=succeeded,
        failed=failed,
    )


@app.post(
    "/v1/appeals",
    response_model=PublicAppealCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def post_public_appeal(
    request: PublicAppealCreateRequest,
    _: None = Depends(require_api_key),
    __: None = Depends(enforce_rate_limit),
) -> PublicAppealCreateResponse:
    if _coerce_request_id(request.decision_request_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="decision_request_id contains invalid characters",
        )
    record = appeals_runtime.create_appeal(
        AdminAppealCreateRequest(
            original_decision_id=request.decision_request_id,
            request_id=request.decision_request_id,
            original_action=request.original_action,
            original_reason_codes=request.original_reason_codes,
            original_model_version=request.original_model_version,
            original_lexicon_version=request.original_lexicon_version,
            original_policy_version=request.original_policy_version,
            original_pack_versions=request.original_pack_versions,
            rationale=request.reason,
        ),
        submitted_by="public-api",
    )
    return PublicAppealCreateResponse(
        appeal_id=record.id,
        status="submitted",
        request_id=record.request_id,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[no-untyped-def]
    request_id = getattr(request.state, "request_id", str(uuid4()))
    payload = ErrorResponse(
        error_code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        request_id=request_id,
    )
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
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
    )
    payload = ErrorResponse(
        error_code="HTTP_500",
        message="Internal server error",
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={"X-Request-ID": request_id},
        content=payload.model_dump(),
    )
