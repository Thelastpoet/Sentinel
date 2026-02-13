from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sentinel_api.async_priority import Priority, async_queue_metrics
from sentinel_core.async_state_machine import validate_queue_transition

PRIORITY_ORDER: dict[str, int] = {
    "critical": 1,
    "urgent": 2,
    "standard": 3,
    "batch": 4,
}

DEFAULT_MAX_RETRY_ATTEMPTS = 5
DEFAULT_MAX_ERROR_RETRY_SECONDS = 3600


@dataclass(frozen=True)
class QueueWorkItem:
    queue_id: int
    event_id: int
    state: str
    priority: Priority
    attempt_count: int
    sla_due_at: datetime
    request_id: str | None
    source: str
    source_event_id: str | None
    lang: str | None
    content_hash: str | None
    payload: dict[str, Any]
    observed_at: datetime
    ingested_at: datetime


@dataclass(frozen=True)
class WorkerRunReport:
    status: str
    queue_id: int | None = None
    proposal_id: int | None = None
    cluster_id: int | None = None
    error: str | None = None


def _get_psycopg_module():
    return importlib.import_module("psycopg")


def _priority_case_sql() -> str:
    return (
        "CASE q.priority "
        "WHEN 'critical' THEN 1 "
        "WHEN 'urgent' THEN 2 "
        "WHEN 'standard' THEN 3 "
        "WHEN 'batch' THEN 4 "
        "ELSE 5 END"
    )


def _coerce_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _build_cluster_key(item: QueueWorkItem) -> str:
    if item.content_hash:
        return f"content:{item.content_hash}"
    payload_repr = json.dumps(item.payload, sort_keys=True, ensure_ascii=True)
    seed = "|".join(
        [
            item.source,
            item.source_event_id or "",
            item.lang or "",
            payload_repr,
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"event:{digest}"


def _policy_impact_summary(item: QueueWorkItem) -> str:
    return f"source={item.source} priority={item.priority} lang={item.lang or 'unknown'}"


def _retry_delay_seconds(
    *,
    base_retry_seconds: int,
    attempt_count: int,
    max_retry_seconds: int,
) -> int:
    base = max(1, base_retry_seconds)
    attempts = max(1, attempt_count)
    cap = max(1, max_retry_seconds)
    delay = base * (2 ** (attempts - 1))
    return min(cap, delay)


def _can_retry(*, attempt_count: int, max_retry_attempts: int) -> bool:
    limit = max(1, max_retry_attempts)
    return attempt_count < limit


def _claim_next_queue_item(cur) -> QueueWorkItem | None:
    cur.execute(
        f"""
        SELECT
          q.id,
          q.event_id,
          q.state,
          q.priority,
          q.attempt_count,
          q.sla_due_at,
          e.request_id,
          e.source,
          e.source_event_id,
          e.lang,
          e.content_hash,
          e.payload,
          e.observed_at,
          e.ingested_at
        FROM monitoring_queue AS q
        JOIN monitoring_events AS e
          ON e.id = q.event_id
        WHERE q.state = 'queued'
          AND (q.next_attempt_at IS NULL OR q.next_attempt_at <= NOW())
        ORDER BY {_priority_case_sql()} ASC, q.created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        return None
    return QueueWorkItem(
        queue_id=int(row[0]),
        event_id=int(row[1]),
        state=str(row[2]),
        priority=str(row[3]),  # type: ignore[arg-type]
        attempt_count=int(row[4]),
        sla_due_at=_normalize_timestamp(row[5]),
        request_id=str(row[6]) if row[6] is not None else None,
        source=str(row[7]),
        source_event_id=str(row[8]) if row[8] is not None else None,
        lang=str(row[9]) if row[9] is not None else None,
        content_hash=str(row[10]) if row[10] is not None else None,
        payload=_coerce_payload(row[11]),
        observed_at=_normalize_timestamp(row[12]),
        ingested_at=_normalize_timestamp(row[13]),
    )


def _write_queue_audit(
    cur,
    *,
    queue_id: int,
    from_state: str | None,
    to_state: str,
    actor: str,
    details: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO monitoring_queue_audit
          (queue_id, from_state, to_state, actor, details)
        VALUES
          (%s, %s, %s, %s, %s)
        """,
        (queue_id, from_state, to_state, actor, details),
    )


def _transition_queue_state(
    cur,
    *,
    queue_id: int,
    from_state: str,
    to_state: str,
    actor: str,
    assigned_worker: str | None = None,
    details: str | None = None,
    last_error: str | None = None,
    next_attempt_at: datetime | None = None,
    increment_attempt: bool = False,
) -> None:
    validate_queue_transition(from_state, to_state)
    attempt_delta = 1 if increment_attempt else 0
    cur.execute(
        """
        UPDATE monitoring_queue
        SET state = %s,
            attempt_count = attempt_count + %s,
            next_attempt_at = %s,
            assigned_worker = COALESCE(%s, assigned_worker),
            last_error = %s,
            last_actor = %s,
            state_updated_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            to_state,
            attempt_delta,
            next_attempt_at,
            assigned_worker,
            last_error,
            actor,
            queue_id,
        ),
    )
    _write_queue_audit(
        cur,
        queue_id=queue_id,
        from_state=from_state,
        to_state=to_state,
        actor=actor,
        details=details,
    )


def _upsert_cluster(cur, item: QueueWorkItem) -> int:
    cluster_key = _build_cluster_key(item)
    summary = _policy_impact_summary(item)
    cur.execute(
        """
        INSERT INTO monitoring_clusters
          (cluster_key, lang, state, signal_count, summary, first_seen_at, last_seen_at, updated_at)
        VALUES
          (%s, %s, 'proposed', 1, %s, %s, %s, NOW())
        ON CONFLICT (cluster_key)
        DO UPDATE SET
          signal_count = monitoring_clusters.signal_count + 1,
          lang = COALESCE(EXCLUDED.lang, monitoring_clusters.lang),
          summary = EXCLUDED.summary,
          state = 'proposed',
          last_seen_at = GREATEST(
            COALESCE(monitoring_clusters.last_seen_at, EXCLUDED.last_seen_at),
            EXCLUDED.last_seen_at
          ),
          updated_at = NOW()
        RETURNING id
        """,
        (
            cluster_key,
            item.lang,
            summary,
            item.observed_at,
            item.observed_at,
        ),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError("failed to upsert monitoring cluster")
    return int(row[0])


def _insert_proposal(cur, item: QueueWorkItem, *, cluster_id: int, actor: str) -> int:
    title = f"Async proposal: {item.source}"
    description = (
        f"source_event_id={item.source_event_id or 'n/a'} request_id={item.request_id or 'n/a'}"
    )
    evidence = json.dumps(
        [
            {
                "event_id": item.event_id,
                "request_id": item.request_id,
                "source": item.source,
                "source_event_id": item.source_event_id,
                "content_hash": item.content_hash,
                "lang": item.lang,
                "priority": item.priority,
            }
        ],
        sort_keys=True,
    )
    cur.execute(
        """
        INSERT INTO release_proposals
          (
            proposal_type,
            status,
            queue_id,
            cluster_id,
            title,
            description,
            evidence,
            policy_impact_summary,
            proposed_by,
            updated_at
          )
        VALUES
          ('lexicon', 'draft', %s, %s, %s, %s, %s::jsonb, %s, %s, NOW())
        RETURNING id
        """,
        (
            item.queue_id,
            cluster_id,
            title,
            description,
            evidence,
            _policy_impact_summary(item),
            actor,
        ),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError("failed to insert release proposal")
    proposal_id = int(row[0])
    cur.execute(
        """
        INSERT INTO release_proposal_audit
          (proposal_id, from_status, to_status, actor, details)
        VALUES
          (%s, %s, 'draft', %s, %s)
        """,
        (proposal_id, None, actor, f"queue_id={item.queue_id} cluster_id={cluster_id}"),
    )
    return proposal_id


def _refresh_queue_depth_metrics(cur) -> None:
    cur.execute(
        """
        SELECT priority, COUNT(1)
        FROM monitoring_queue
        WHERE state IN ('queued', 'processing', 'clustered')
        GROUP BY priority
        """
    )
    depth_map = {str(row[0]): int(row[1]) for row in cur.fetchall()}
    for priority in ("critical", "urgent", "standard", "batch"):
        async_queue_metrics.set_queue_depth(cast(Priority, priority), depth_map.get(priority, 0))


def process_one(
    database_url: str,
    *,
    worker_id: str = "async-worker",
    error_retry_seconds: int = 120,
    max_retry_attempts: int = DEFAULT_MAX_RETRY_ATTEMPTS,
    max_error_retry_seconds: int = DEFAULT_MAX_ERROR_RETRY_SECONDS,
) -> WorkerRunReport:
    psycopg = _get_psycopg_module()
    claimed_item: QueueWorkItem | None = None
    with psycopg.connect(database_url) as conn:
        try:
            with conn.cursor() as cur:
                claimed_item = _claim_next_queue_item(cur)
                if claimed_item is None:
                    _refresh_queue_depth_metrics(cur)
                    conn.commit()
                    return WorkerRunReport(status="idle")

                _transition_queue_state(
                    cur,
                    queue_id=claimed_item.queue_id,
                    from_state="queued",
                    to_state="processing",
                    actor=worker_id,
                    assigned_worker=worker_id,
                    increment_attempt=True,
                    details=f"event_id={claimed_item.event_id}",
                )

                now = datetime.now(tz=UTC)
                if now > claimed_item.sla_due_at:
                    async_queue_metrics.increment_sla_breach(claimed_item.priority)

                cluster_id = _upsert_cluster(cur, claimed_item)
                proposal_id = _insert_proposal(
                    cur,
                    claimed_item,
                    cluster_id=cluster_id,
                    actor=worker_id,
                )

                _transition_queue_state(
                    cur,
                    queue_id=claimed_item.queue_id,
                    from_state="processing",
                    to_state="clustered",
                    actor=worker_id,
                    assigned_worker=worker_id,
                    details=f"cluster_id={cluster_id}",
                )
                _transition_queue_state(
                    cur,
                    queue_id=claimed_item.queue_id,
                    from_state="clustered",
                    to_state="proposed",
                    actor=worker_id,
                    assigned_worker=worker_id,
                    details=f"proposal_id={proposal_id}",
                )

                _refresh_queue_depth_metrics(cur)
            conn.commit()
            return WorkerRunReport(
                status="processed",
                queue_id=claimed_item.queue_id,
                proposal_id=proposal_id,
                cluster_id=cluster_id,
            )
        except Exception as exc:
            conn.rollback()
            if claimed_item is not None:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT state FROM monitoring_queue WHERE id = %s FOR UPDATE",
                        (claimed_item.queue_id,),
                    )
                    row = cur.fetchone()
                    if row is not None and str(row[0]) == "processing":
                        current_attempt_count = claimed_item.attempt_count + 1
                        _transition_queue_state(
                            cur,
                            queue_id=claimed_item.queue_id,
                            from_state="processing",
                            to_state="error",
                            actor=worker_id,
                            assigned_worker=worker_id,
                            details="worker exception",
                            last_error=str(exc),
                        )
                        if _can_retry(
                            attempt_count=current_attempt_count,
                            max_retry_attempts=max_retry_attempts,
                        ):
                            retry_delay_seconds = _retry_delay_seconds(
                                base_retry_seconds=error_retry_seconds,
                                attempt_count=current_attempt_count,
                                max_retry_seconds=max_error_retry_seconds,
                            )
                            _transition_queue_state(
                                cur,
                                queue_id=claimed_item.queue_id,
                                from_state="error",
                                to_state="queued",
                                actor=worker_id,
                                assigned_worker=worker_id,
                                details=(
                                    "retry scheduled "
                                    f"attempt_count={current_attempt_count} "
                                    f"delay_seconds={retry_delay_seconds}"
                                ),
                                last_error=str(exc),
                                next_attempt_at=datetime.now(tz=UTC)
                                + timedelta(seconds=retry_delay_seconds),
                            )
                        else:
                            _transition_queue_state(
                                cur,
                                queue_id=claimed_item.queue_id,
                                from_state="error",
                                to_state="dropped",
                                actor=worker_id,
                                assigned_worker=worker_id,
                                details=(
                                    "max retry attempts exhausted "
                                    f"attempt_count={current_attempt_count}"
                                ),
                                last_error=str(exc),
                            )
                    _refresh_queue_depth_metrics(cur)
                conn.commit()
            return WorkerRunReport(
                status="error",
                queue_id=claimed_item.queue_id if claimed_item is not None else None,
                error=str(exc),
            )


def process_batch(
    database_url: str,
    *,
    worker_id: str = "async-worker",
    max_items: int = 20,
    error_retry_seconds: int = 120,
    max_retry_attempts: int = DEFAULT_MAX_RETRY_ATTEMPTS,
    max_error_retry_seconds: int = DEFAULT_MAX_ERROR_RETRY_SECONDS,
) -> list[WorkerRunReport]:
    reports: list[WorkerRunReport] = []
    for _ in range(max(1, max_items)):
        report = process_one(
            database_url,
            worker_id=worker_id,
            error_retry_seconds=error_retry_seconds,
            max_retry_attempts=max_retry_attempts,
            max_error_retry_seconds=max_error_retry_seconds,
        )
        reports.append(report)
        if report.status == "idle":
            break
    return reports
