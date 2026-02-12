# ADR-0006: Security Controls Roadmap (Phased)

- Status: Accepted
- Date: 2026-02-12
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0001-v1-moderation-api.md`, `docs/specs/rfcs/0002-async-monitoring-update-system.md`

## Context

`docs/master.md` requires election-grade controls (OAuth, mTLS, RBAC/JIT, MFA, tamper-evident logs). Current implementation is intentionally minimal (API key + rate limiting). Without a dated roadmap, delivery will drift and pre-election risk will remain implicit.

## Decision

Adopt the phased security roadmap below as a binding delivery plan.

| Stage | Deadline | Control set | Enforcement gate |
|---|---|---|---|
| S0 (baseline) | 2026-03-31 | API key auth + deterministic rate limits | Required for all environments |
| S1 | 2026-06-30 | OAuth2 client-credentials for internal/admin APIs; scoped credentials | No new internal/admin endpoint without OAuth scope check |
| S2 | 2026-09-30 | mTLS for high-risk connector ingestion and partner webhooks | High-risk connectors must reject non-mTLS traffic |
| S3 | 2026-11-30 | RBAC + just-in-time elevation for release/policy promotion actions | Promotion endpoints require role checks and elevation audit trail |
| S4 | 2027-01-31 | Mandatory MFA for privileged operational access | Privileged access disallowed without MFA |
| S5 | 2027-03-31 | Tamper-evident audit logs (hash chain + verification task) | Daily verification job must pass before deployment promotion |

## Rationale

- Converts broad security intent into measurable deadlines.
- Aligns controls with election-readiness windows.
- Improves reviewer clarity for security-impacting PRs.

## Consequences

- Positive:
  - Clear accountability and stage-gated delivery.
  - Reduced ambiguity for contributors and maintainers.
- Negative:
  - Additional integration work and operational complexity.
- Neutral:
  - Baseline API-key behavior remains valid only until S1/S2 controls apply per endpoint class.

## Alternatives Considered

1. Keep security targets only in narrative docs.
   - Rejected: no enforceable delivery pressure.
2. Implement all controls in one milestone.
   - Rejected: high delivery risk and unclear rollback options.

## Implementation Notes

- Every stage requires:
  - explicit schema/config updates
  - rollback plan
  - test evidence in PR
- Security stage completion criteria:
  - control implemented
  - contract/behavior documented
  - negative-path tests added
  - operations runbook updated
- Missing a deadline requires updating `docs/specs/tasks.md` with risk and recovery plan in the same PR.
