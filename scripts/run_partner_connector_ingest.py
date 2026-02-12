from __future__ import annotations

import argparse
import os
from datetime import datetime

from sentinel_api.partner_connectors import (
    JsonFileFactCheckConnector,
    PartnerConnectorIngestionService,
    ResilientPartnerConnector,
)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest partner fact-check signals into monitoring queue."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("SENTINEL_DATABASE_URL"),
        help="Postgres connection URL. Defaults to SENTINEL_DATABASE_URL.",
    )
    parser.add_argument(
        "--connector-name",
        default=os.getenv("SENTINEL_PARTNER_CONNECTOR_NAME", "factcheck-file"),
        help="Logical connector name stored in monitoring_events.source.",
    )
    parser.add_argument(
        "--input-path",
        required=True,
        help="Path to JSON or JSONL partner signal file.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Optional ISO-8601 filter for records observed after this timestamp.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max signals to fetch from connector in this run.",
    )
    parser.add_argument(
        "--actor",
        default=os.getenv("SENTINEL_CONNECTOR_INGEST_ACTOR", "connector-ingest"),
        help="Audit actor for queue ingress events.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Connector fetch attempts before reporting error.",
    )
    parser.add_argument(
        "--base-backoff-seconds",
        type=int,
        default=2,
        help="Base retry delay in seconds.",
    )
    parser.add_argument(
        "--max-backoff-seconds",
        type=int,
        default=60,
        help="Maximum retry delay in seconds.",
    )
    parser.add_argument(
        "--circuit-failure-threshold",
        type=int,
        default=3,
        help="Consecutive failed runs before opening circuit.",
    )
    parser.add_argument(
        "--circuit-reset-seconds",
        type=int,
        default=120,
        help="Circuit open duration before retry is allowed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("SENTINEL_DATABASE_URL or --database-url is required")

    connector = JsonFileFactCheckConnector(
        name=args.connector_name, input_path=args.input_path
    )
    resilient_connector = ResilientPartnerConnector(
        connector,
        max_attempts=args.max_attempts,
        base_backoff_seconds=args.base_backoff_seconds,
        max_backoff_seconds=args.max_backoff_seconds,
        circuit_failure_threshold=args.circuit_failure_threshold,
        circuit_reset_seconds=args.circuit_reset_seconds,
    )
    service = PartnerConnectorIngestionService(
        database_url=args.database_url,
        connector_name=args.connector_name,
        connector=resilient_connector,
        actor=args.actor,
    )
    try:
        since_dt = _parse_datetime(args.since)
    except ValueError as exc:
        raise SystemExit(f"--since must be ISO-8601 datetime: {exc}") from exc

    report = service.ingest_once(since=since_dt, limit=args.limit)
    print(
        "connector-status="
        f"{report.status} connector={report.connector_name} "
        f"fetched={report.fetched_count} queued={report.queued_count} "
        f"deduplicated={report.deduplicated_count} invalid={report.invalid_count} "
        f"attempts={report.attempts} retry_delays={report.retry_delays_seconds} "
        f"error={report.error}"
    )
    if report.status == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
