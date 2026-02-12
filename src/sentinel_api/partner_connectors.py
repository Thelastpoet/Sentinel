from __future__ import annotations

import hashlib
import importlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from sentinel_api.async_priority import Priority, PrioritySignals, classify_priority, sla_due_at


ConnectorStatus = Literal["ok", "error", "circuit_open"]


@dataclass(frozen=True)
class PartnerSignal:
    source_event_id: str
    text: str
    observed_at: datetime
    request_id: str | None = None
    lang: str | None = None
    reliability_score: int | None = None
    imminent_violence: bool = False
    campaign_disinfo_spike: bool = False
    is_backfill: bool = False
    manual_priority: Priority | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class PartnerConnector(Protocol):
    name: str

    def fetch_signals(
        self, *, since: datetime | None = None, limit: int = 100
    ) -> list[PartnerSignal]:
        ...


class _JsonFileSignalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_event_id: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=5000)
    observed_at: datetime
    request_id: str | None = Field(default=None, max_length=128)
    lang: str | None = Field(default=None, max_length=16)
    reliability_score: int | None = Field(default=None, ge=1, le=5)
    imminent_violence: bool = False
    campaign_disinfo_spike: bool = False
    is_backfill: bool = False
    manual_priority: Priority | None = None
    payload: dict[str, Any] | None = None


class JsonFileFactCheckConnector:
    def __init__(self, *, name: str, input_path: str | Path) -> None:
        self.name = name.strip() or "factcheck-file"
        self.input_path = Path(input_path)

    def _load_records(self) -> list[dict[str, Any]]:
        if not self.input_path.exists():
            raise ValueError(f"connector input file does not exist: {self.input_path}")
        raw = self.input_path.read_text(encoding="utf-8")
        suffix = self.input_path.suffix.lower()
        if suffix == ".json":
            payload = json.loads(raw)
            if not isinstance(payload, list):
                raise ValueError("JSON connector input must be an array")
            if not all(isinstance(item, dict) for item in payload):
                raise ValueError("JSON connector input array must contain objects")
            return [dict(item) for item in payload]
        records: list[dict[str, Any]] = []
        for index, line in enumerate(raw.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(
                    f"JSONL connector input line {index} must be an object"
                )
            records.append(payload)
        return records

    def fetch_signals(
        self, *, since: datetime | None = None, limit: int = 100
    ) -> list[PartnerSignal]:
        effective_limit = max(1, min(limit, 5000))
        normalized_since = _normalize_timestamp(since) if since is not None else None
        rows = self._load_records()
        signals: list[PartnerSignal] = []
        for row in rows:
            record = _JsonFileSignalRecord.model_validate(row)
            observed_at = _normalize_timestamp(record.observed_at)
            if normalized_since is not None and observed_at <= normalized_since:
                continue
            payload = dict(record.payload or {})
            if "text" not in payload:
                payload["text"] = record.text
            signals.append(
                PartnerSignal(
                    source_event_id=record.source_event_id,
                    text=record.text,
                    observed_at=observed_at,
                    request_id=record.request_id,
                    lang=record.lang,
                    reliability_score=record.reliability_score,
                    imminent_violence=record.imminent_violence,
                    campaign_disinfo_spike=record.campaign_disinfo_spike,
                    is_backfill=record.is_backfill,
                    manual_priority=record.manual_priority,
                    payload=payload,
                )
            )
        signals.sort(key=lambda item: (item.observed_at, item.source_event_id))
        return signals[:effective_limit]


@dataclass(frozen=True)
class ConnectorFetchOutcome:
    status: ConnectorStatus
    connector_name: str
    signals: list[PartnerSignal] = field(default_factory=list)
    attempts: int = 0
    retry_delays_seconds: list[int] = field(default_factory=list)
    error: str | None = None


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _retry_delay_seconds(*, attempt: int, base: int, cap: int) -> int:
    normalized_attempt = max(1, attempt)
    normalized_base = max(1, base)
    normalized_cap = max(1, cap)
    return min(normalized_cap, normalized_base * (2 ** (normalized_attempt - 1)))


class ResilientPartnerConnector:
    def __init__(
        self,
        connector: PartnerConnector,
        *,
        max_attempts: int = 3,
        base_backoff_seconds: int = 2,
        max_backoff_seconds: int = 60,
        circuit_failure_threshold: int = 3,
        circuit_reset_seconds: int = 120,
        sleep_fn=time.sleep,
        clock_fn=_now_utc,
    ) -> None:
        self.connector = connector
        self.max_attempts = max(1, max_attempts)
        self.base_backoff_seconds = max(1, base_backoff_seconds)
        self.max_backoff_seconds = max(1, max_backoff_seconds)
        self.circuit_failure_threshold = max(1, circuit_failure_threshold)
        self.circuit_reset_seconds = max(1, circuit_reset_seconds)
        self._sleep_fn = sleep_fn
        self._clock_fn = clock_fn
        self._consecutive_failures = 0
        self._circuit_open_until: datetime | None = None

    def _is_circuit_open(self, now: datetime) -> bool:
        if self._circuit_open_until is None:
            return False
        if now >= self._circuit_open_until:
            return False
        return True

    def fetch_signals(
        self, *, since: datetime | None = None, limit: int = 100
    ) -> ConnectorFetchOutcome:
        now = _normalize_timestamp(self._clock_fn())
        if self._is_circuit_open(now):
            return ConnectorFetchOutcome(
                status="circuit_open",
                connector_name=self.connector.name,
                error=(
                    "circuit open until "
                    f"{self._circuit_open_until.isoformat()}"
                    if self._circuit_open_until is not None
                    else "circuit open"
                ),
            )

        if self._circuit_open_until is not None and now >= self._circuit_open_until:
            self._circuit_open_until = None

        retry_delays: list[int] = []
        last_error: str | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                signals = self.connector.fetch_signals(since=since, limit=limit)
                self._consecutive_failures = 0
                self._circuit_open_until = None
                return ConnectorFetchOutcome(
                    status="ok",
                    connector_name=self.connector.name,
                    signals=signals,
                    attempts=attempt,
                    retry_delays_seconds=retry_delays,
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt < self.max_attempts:
                    delay_seconds = _retry_delay_seconds(
                        attempt=attempt,
                        base=self.base_backoff_seconds,
                        cap=self.max_backoff_seconds,
                    )
                    retry_delays.append(delay_seconds)
                    self._sleep_fn(delay_seconds)

        self._consecutive_failures += 1
        if self._consecutive_failures >= self.circuit_failure_threshold:
            self._circuit_open_until = _normalize_timestamp(self._clock_fn()) + timedelta(
                seconds=self.circuit_reset_seconds
            )

        return ConnectorFetchOutcome(
            status="error",
            connector_name=self.connector.name,
            attempts=self.max_attempts,
            retry_delays_seconds=retry_delays,
            error=last_error,
        )


@dataclass(frozen=True)
class ConnectorIngestReport:
    connector_name: str
    status: ConnectorStatus
    fetched_count: int
    queued_count: int
    deduplicated_count: int
    invalid_count: int
    attempts: int
    retry_delays_seconds: list[int]
    error: str | None = None


def _content_hash_for_signal(signal: PartnerSignal) -> str:
    payload_repr = json.dumps(signal.payload, sort_keys=True, ensure_ascii=True)
    seed = "|".join([signal.text, signal.source_event_id, payload_repr])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _policy_impact_summary(
    signal: PartnerSignal, *, connector_name: str, priority: Priority
) -> str:
    return (
        f"source={connector_name} priority={priority} "
        f"lang={signal.lang or 'unknown'} reliability={signal.reliability_score}"
    )


def _build_priority(signal: PartnerSignal) -> Priority:
    return classify_priority(
        PrioritySignals(
            imminent_violence=signal.imminent_violence,
            campaign_disinfo_spike=signal.campaign_disinfo_spike,
            source_reliability=signal.reliability_score,
            is_backfill=signal.is_backfill,
            manual_priority=signal.manual_priority,
        )
    )


class PartnerConnectorIngestionService:
    def __init__(
        self,
        *,
        database_url: str,
        connector_name: str,
        connector: ResilientPartnerConnector,
        actor: str = "connector-ingest",
    ) -> None:
        self.database_url = database_url
        self.connector_name = connector_name
        self.connector = connector
        self.actor = actor

    def ingest_once(
        self, *, since: datetime | None = None, limit: int = 100
    ) -> ConnectorIngestReport:
        outcome = self.connector.fetch_signals(since=since, limit=limit)
        if outcome.status != "ok":
            return ConnectorIngestReport(
                connector_name=outcome.connector_name,
                status=outcome.status,
                fetched_count=0,
                queued_count=0,
                deduplicated_count=0,
                invalid_count=0,
                attempts=outcome.attempts,
                retry_delays_seconds=list(outcome.retry_delays_seconds),
                error=outcome.error,
            )

        queued_count = 0
        deduplicated_count = 0
        invalid_count = 0
        psycopg = importlib.import_module("psycopg")
        try:
            with psycopg.connect(self.database_url) as conn:
                with conn.cursor() as cur:
                    for signal in outcome.signals:
                        try:
                            priority = _build_priority(signal)
                        except ValueError:
                            invalid_count += 1
                            continue

                        cur.execute(
                            """
                            INSERT INTO monitoring_events
                              (
                                request_id,
                                source,
                                source_event_id,
                                lang,
                                content_hash,
                                reliability_score,
                                payload,
                                observed_at,
                                ingested_at,
                                updated_at
                              )
                            VALUES
                              (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, NOW(), NOW())
                            ON CONFLICT (source, source_event_id)
                            WHERE source_event_id IS NOT NULL
                            DO UPDATE SET
                              request_id = COALESCE(EXCLUDED.request_id, monitoring_events.request_id),
                              lang = COALESCE(EXCLUDED.lang, monitoring_events.lang),
                              content_hash = EXCLUDED.content_hash,
                              reliability_score = EXCLUDED.reliability_score,
                              payload = EXCLUDED.payload,
                              observed_at = GREATEST(monitoring_events.observed_at, EXCLUDED.observed_at),
                              updated_at = NOW()
                            RETURNING id
                            """,
                            (
                                signal.request_id,
                                self.connector_name,
                                signal.source_event_id,
                                signal.lang,
                                _content_hash_for_signal(signal),
                                signal.reliability_score,
                                json.dumps(signal.payload, sort_keys=True),
                                _normalize_timestamp(signal.observed_at),
                            ),
                        )
                        event_row = cur.fetchone()
                        if event_row is None:
                            invalid_count += 1
                            continue
                        event_id = int(event_row[0])
                        queued_at = _now_utc()
                        cur.execute(
                            """
                            INSERT INTO monitoring_queue
                              (
                                event_id,
                                priority,
                                state,
                                attempt_count,
                                sla_due_at,
                                policy_impact_summary,
                                last_actor,
                                state_updated_at,
                                updated_at
                              )
                            VALUES
                              (%s, %s, 'queued', 0, %s, %s, %s, NOW(), NOW())
                            ON CONFLICT (event_id) DO NOTHING
                            RETURNING id
                            """,
                            (
                                event_id,
                                priority,
                                sla_due_at(priority, queued_at),
                                _policy_impact_summary(
                                    signal,
                                    connector_name=self.connector_name,
                                    priority=priority,
                                ),
                                self.actor,
                            ),
                        )
                        queue_row = cur.fetchone()
                        if queue_row is None:
                            deduplicated_count += 1
                            continue
                        queued_count += 1
                        queue_id = int(queue_row[0])
                        cur.execute(
                            """
                            INSERT INTO monitoring_queue_audit
                              (queue_id, from_state, to_state, actor, details)
                            VALUES
                              (%s, %s, 'queued', %s, %s)
                            """,
                            (
                                queue_id,
                                None,
                                self.actor,
                                f"source={self.connector_name} event_id={event_id}",
                            ),
                        )
                conn.commit()
        except Exception as exc:
            return ConnectorIngestReport(
                connector_name=outcome.connector_name,
                status="error",
                fetched_count=len(outcome.signals),
                queued_count=queued_count,
                deduplicated_count=deduplicated_count,
                invalid_count=invalid_count,
                attempts=outcome.attempts,
                retry_delays_seconds=list(outcome.retry_delays_seconds),
                error=str(exc),
            )

        return ConnectorIngestReport(
            connector_name=outcome.connector_name,
            status="ok",
            fetched_count=len(outcome.signals),
            queued_count=queued_count,
            deduplicated_count=deduplicated_count,
            invalid_count=invalid_count,
            attempts=outcome.attempts,
            retry_delays_seconds=list(outcome.retry_delays_seconds),
        )
