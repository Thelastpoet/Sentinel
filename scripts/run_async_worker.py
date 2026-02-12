from __future__ import annotations

import argparse
import os
import time

from sentinel_api.async_worker import process_batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run async monitoring worker against Postgres queue."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("SENTINEL_DATABASE_URL"),
        help="Postgres connection URL. Defaults to SENTINEL_DATABASE_URL.",
    )
    parser.add_argument(
        "--worker-id",
        default=os.getenv("SENTINEL_ASYNC_WORKER_ID", "async-worker"),
        help="Worker identity used in audit trails.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="Max items to process per batch.",
    )
    parser.add_argument(
        "--error-retry-seconds",
        type=int,
        default=120,
        help="Requeue delay for error transitions.",
    )
    parser.add_argument(
        "--max-retry-attempts",
        type=int,
        default=5,
        help="Maximum processing attempts before dropping a queue item.",
    )
    parser.add_argument(
        "--max-error-retry-seconds",
        type=int,
        default=3600,
        help="Upper bound for exponential retry delay after worker errors.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Continuously poll and process batches.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=2.0,
        help="Sleep interval between loop batches when idle.",
    )
    return parser.parse_args()


def run_once(args: argparse.Namespace) -> int:
    reports = process_batch(
        args.database_url,
        worker_id=args.worker_id,
        max_items=args.max_items,
        error_retry_seconds=args.error_retry_seconds,
        max_retry_attempts=args.max_retry_attempts,
        max_error_retry_seconds=args.max_error_retry_seconds,
    )
    for report in reports:
        print(
            "worker-status="
            f"{report.status} queue_id={report.queue_id} "
            f"cluster_id={report.cluster_id} proposal_id={report.proposal_id} "
            f"error={report.error}"
        )
    if any(report.status == "error" for report in reports):
        return 1
    return 0


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("SENTINEL_DATABASE_URL or --database-url is required")

    if not args.loop:
        raise SystemExit(run_once(args))

    while True:
        exit_code = run_once(args)
        if exit_code != 0:
            raise SystemExit(exit_code)
        time.sleep(max(0.1, args.poll_interval_seconds))


if __name__ == "__main__":
    main()
