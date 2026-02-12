# I-404: Partner Fact-Check Connector Framework

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Connector abstraction, resilient fetch behavior, and reference ingest connector
- Task linkage: `I-404` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 9.2, Sec. 14, Sec. 21.1), `docs/specs/rfcs/0002-async-monitoring-update-system.md`

## 1. Objective

Deliver a replaceable partner-ingest framework with resilience controls:

1. connector abstraction decoupled from downstream queue processing;
2. retry with exponential backoff for transient partner failures;
3. circuit-breaker guardrail to prevent repeated upstream hammering.

## 2. Runtime Surface

- Core module: `src/sentinel_api/partner_connectors.py`
- Runner CLI: `scripts/run_partner_connector_ingest.py`
- Make shortcut: `make connector-ingest CONNECTOR=<name> INPUT=<path>`

Reference connector:

- `JsonFileFactCheckConnector` for JSON/JSONL partner feeds.

## 3. Resilience Behavior

- Retry attempts: configurable (`max_attempts`, `base_backoff_seconds`, `max_backoff_seconds`).
- Backoff: exponential with cap.
- Circuit breaker:
  - opens after configurable consecutive failed fetch runs;
  - returns `circuit_open` without calling connector while open;
  - automatically retries after reset window.

## 4. Ingest Behavior

- Ingest writes/upserts `monitoring_events` by `(source, source_event_id)`.
- Queue insert is idempotent via unique `monitoring_queue(event_id)`:
  - new items become `queued`;
  - duplicates are counted as `deduplicated_count`.
- Priority assignment uses existing async priority classifier with signal metadata.

## 5. Contract Artifacts

Internal schemas added:

- `docs/specs/schemas/internal/partner-connector-signal.schema.json`
- `docs/specs/schemas/internal/partner-connector-ingest-report.schema.json`

`scripts/check_contract.py` validates key enums for connector priority/status fields.

## 6. Verification Commands

```bash
python -m pytest -q tests/test_partner_connectors.py
SENTINEL_INTEGRATION_DB_URL=postgresql://sentinel:sentinel@localhost:5432/sentinel python -m pytest -q tests/test_partner_connector_ingest_integration.py
python scripts/check_contract.py
python -m pytest -q
```
