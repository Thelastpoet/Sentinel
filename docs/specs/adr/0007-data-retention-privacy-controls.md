# ADR-0007: Data Retention and Privacy Controls

- Status: Accepted
- Date: 2026-02-12
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0001-v1-moderation-api.md`, `docs/specs/rfcs/0002-async-monitoring-update-system.md`, `docs/specs/rfcs/0003-appeals-transparency-workflow.md`

## Context

`docs/master.md` defines retention windows and privacy principles, but enforcement mechanics (record classification, TTL/archival jobs, legal hold, and access auditability) are not yet standardized.

## Decision

Adopt a mandatory record-class retention model with legal-hold and audit controls.

| Record class | Retention policy | Enforcement rule |
|---|---|---|
| `operational_runtime` | 90 days (within 30-90 target) | Auto-delete after TTL unless legal hold |
| `async_monitoring_raw` | 30 days | Auto-delete after TTL unless legal hold |
| `decision_record` | 7 years | Archive, then delete at expiry unless legal hold |
| `governance_audit` | 7 years | Immutable append-only log with expiry control |
| `analytics_aggregate` | long-term anonymized | No direct identifiers allowed |
| `legal_hold` | policy-driven | Overrides deletion until hold removed |

## Rationale

- Makes compliance enforceable instead of aspirational.
- Reduces privacy and legal risk through deterministic lifecycle controls.
- Supports transparent audit and appeals reconstruction requirements.

## Consequences

- Positive:
  - Predictable data lifecycle and stronger compliance posture.
  - Clear operational accountability for deletion and archival.
- Negative:
  - Additional migration/job orchestration complexity.
- Neutral:
  - Existing data requires one-time classification and backfill.

## Alternatives Considered

1. Manual retention and periodic cleanup.
   - Rejected: high error risk and weak auditability.
2. Single retention window for all data.
   - Rejected: conflicts with legal/audit needs.

## Implementation Notes

Delivery milestones:

| Milestone | Deadline | Required artifact |
|---|---|---|
| D1 | 2026-06-15 | Record-class taxonomy implemented in schema and write paths |
| D2 | 2026-07-31 | Legal-hold model and override checks implemented |
| D3 | 2026-09-15 | Deletion/archival jobs with dry-run reports |
| D4 | 2026-10-31 | Enforced retention in production-like env with audit logs |
| D5 | 2026-12-15 | Privacy access-audit report and PII minimization verification |

Mandatory controls:

- Every delete/archive action must be logged with `actor/system`, timestamp, class, and count.
- Legal-hold checks must run before deletion for every class.
- Privacy review must confirm that analytics exports exclude direct identifiers.
