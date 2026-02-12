# RFC-0002: Async Monitoring and Update System (Election Readiness)

- Status: Approved
- Authors: Core maintainers
- Created: 2026-02-12
- Target milestone: Phase 1 -> Phase 3 bridge
- Related issues: TBD
- Supersedes: None

## 1. Summary

Define Sentinel's asynchronous intelligence pipeline for election-time adaptation: ingest signals, prioritize queue items by risk, generate candidate lexicon/narrative updates, and publish governed release proposals without changing hot-path determinism.

## 2. Problem Statement

The current implementation focuses on hot-path moderation. `docs/master.md` defines async monitoring and update workflows as core scope for 2027 election readiness, but these workflows are not yet specified in actionable detail. Without a formal spec, adaptation speed, queue SLAs, and governance controls will drift.

## 3. Goals

- Specify a deterministic async pipeline with priority SLAs and explicit state transitions.
- Define governed handoff from observed signals to draft release proposals.
- Preserve hot-path stability while enabling weekly-or-faster updates during campaign peaks.

## 4. Non-Goals

- Full model-training pipeline orchestration.
- Public transparency portal UI.
- End-user appeals UI (tracked separately).

## 5. Proposed Behavior

Pipeline stages:

1. Ingest: collect normalized events from connectors and trusted partner inputs.
2. Prioritize: classify into `critical`, `urgent`, `standard`, `batch` queues.
3. Triage: group similar events into candidate clusters (emerging terms/narratives).
4. Propose: emit structured release candidates (`lexicon`, `narrative`, `policy`) with evidence references.
5. Review: human reviewer accepts/rejects/edits candidate with rationale.
6. Promote: accepted candidates become draft release artifacts for existing release governance flow.

Deterministic queue/proposal states and transitions:

| Entity | State | Allowed next states |
|---|---|---|
| `monitoring_queue` | `queued` | `processing`, `dropped` |
| `monitoring_queue` | `processing` | `clustered`, `error` |
| `monitoring_queue` | `clustered` | `proposed`, `dropped` |
| `monitoring_queue` | `proposed` | terminal |
| `monitoring_queue` | `dropped` | terminal |
| `monitoring_queue` | `error` | `queued`, `dropped` |
| `release_proposals` | `draft` | `in_review`, `rejected` |
| `release_proposals` | `in_review` | `approved`, `rejected`, `needs_revision` |
| `release_proposals` | `needs_revision` | `in_review`, `rejected` |
| `release_proposals` | `approved` | `promoted`, `rejected` |
| `release_proposals` | `promoted` | terminal |
| `release_proposals` | `rejected` | terminal |

SLA mapping (from `docs/master.md` section 3.2):

| Priority | Max queue dwell time |
|---|---|
| `critical` | 5 minutes |
| `urgent` | 30 minutes |
| `standard` | 4 hours |
| `batch` | 24 hours |

Each queue item and proposal must carry:

- `request_id`/trace IDs
- language metadata
- source reliability indicator
- policy impact summary
- actor and timestamp for every state transition

## 6. API and Schema Impact

- Public API paths affected: none in initial slice.
- Internal/admin API (new): queue intake, queue list/dequeue, proposal review actions.
- Schema additions (new):
  - `docs/specs/schemas/internal/monitoring-queue-item.schema.json`
  - `docs/specs/schemas/internal/monitoring-cluster.schema.json`
  - `docs/specs/schemas/internal/release-proposal.schema.json`
  - `docs/specs/schemas/internal/proposal-review-event.schema.json`
- Backward compatibility: additive; no breaking changes to `POST /v1/moderate`.

## 7. Policy and Reason Codes

- Hot-path reason codes unchanged in this RFC.
- Async proposals may suggest additions/changes to reason-code mappings, but activation remains governed by release lifecycle controls.

## 8. Architecture and Data Impact

- Components touched: connector ingestion, async worker, triage/clustering service, release governance integration.
- Data model additions:
  - `monitoring_events`
  - `monitoring_queue`
  - `monitoring_clusters`
  - `release_proposals`
  - `proposal_reviews`
- Migration requirements: new tables and indexes for SLA queries and traceability.

## 9. Security, Privacy, and Abuse Considerations

- Enforce source authentication for connector ingestion.
- Minimize PII storage; store only moderation-relevant fields.
- Audit every reviewer action.
- Enforce strict access controls for proposal approval.

## 10. Alternatives Considered

1. Manual-only updates from ad hoc spreadsheets.
   - Rejected: weak auditability and insufficient election-period speed.
2. Fully automated release promotion.
   - Rejected: high policy and legal risk without human accountability.

## 11. Rollout Plan

- Stage 1 (shadow): async ingestion and queue classification only.
- Stage 2 (advisory): proposal generation and reviewer tooling without auto-promotion.
- Stage 3 (enforcement): governed promotion into release lifecycle with defined SLAs.

## 12. Acceptance Criteria

1. Queue priorities map to SLAs from `docs/master.md` section 3.2.
2. Every queue/proposal transition is auditable (`actor`, `timestamp`, `action`, `details`).
3. Release proposals can be promoted through existing release governance flow.
4. No regression to `/v1/moderate` contract or latency SLO due to async workload.

## 13. Test Plan

- Unit tests:
  - queue prioritization classifier
  - allowed state transitions and invalid transition rejection
  - proposal payload validation and required metadata
- Integration tests:
  - ingest -> queue -> cluster -> proposal -> review -> promotion handoff
  - retry/error handling with requeue path
- Contract tests:
  - internal/admin schemas for queue and proposal operations
  - backward compatibility check for `POST /v1/moderate`
- Load tests:
  - campaign surge backlog simulation by priority
  - SLA breach detection and alert firing thresholds

## 14. Observability

- Logs: queue ingress/egress and review transitions with trace IDs.
- Metrics: queue depth by priority, SLA breach count, proposal acceptance rate.
- Traces: connector event to release proposal lineage.
- Alerts: critical queue backlog and SLA breach thresholds.

## 15. Implementation Constraints

1. Async processing must not run on the synchronous moderation request path.
2. Promotion into active moderation behavior continues to use existing release governance controls.
3. Initial implementation may use Postgres-backed queueing if SLA targets are met and monitored.

## 16. Acceptance-to-Verification Mapping

| Acceptance criterion | Verification |
|---|---|
| AC-1 SLA mapping exists and is enforced | Unit tests for priority classifier + integration tests for SLA timers + alert test for breach counter |
| AC-2 All transitions auditable | Integration test asserting audit row creation for every transition |
| AC-3 Proposals can be promoted via release governance | Integration test from `approved` proposal to draft release artifact and governance handoff |
| AC-4 No `/v1/moderate` regression | Contract check + existing moderation test suite + latency benchmark gate |
