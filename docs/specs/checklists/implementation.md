# Implementation Checklist (Spec-Driven)

Use this checklist in every feature PR.

## Spec Readiness

- [ ] RFC exists or is updated
- [ ] RFC status is Approved
- [ ] OpenAPI updated if public behavior changed
- [ ] JSON schemas updated if payloads changed
- [ ] ADR added/updated for architecture-level decisions

## Engineering Readiness

- [ ] Acceptance criteria mapped to tests
- [ ] Backward compatibility documented
- [ ] Migration plan documented (if needed)
- [ ] Feature flags/staged rollout plan documented

## Quality Gates

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Contract tests pass
- [ ] Latency impact assessed (P95 budget)
- [ ] Reason codes and evidence traces verified

## Operations and Governance

- [ ] Observability added (logs/metrics/traces)
- [ ] Security/privacy impacts reviewed
- [ ] Changelog entry added
- [ ] Reviewer checklist completed
