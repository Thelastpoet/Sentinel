# Sentinel Spec Task Board

Last updated: 2026-02-12

Scope note: this board currently tracks phase-aligned spec/governance milestones.
Implementation tasks are opened only after the corresponding phase specs are approved.

Status legend:

- `todo`: not started
- `in_progress`: actively being implemented
- `blocked`: waiting on dependency/decision
- `done`: implemented and verified

## Phase Roadmap

| Phase | Window | Goal | Gate |
|---|---|---|---|
| Phase 1: Foundation | Months 1-6 | Stable hot-path API and deterministic governance baseline | All Phase 1 tasks `done` |
| Phase 2: Intelligence Integration | Months 7-12 | Define async intelligence/update pipeline and control plane specs | T-017, T-020, T-021 `done` |
| Phase 3: Election Readiness | Months 13-18 | Codify election-time controls, appeals, and transparency workflows | T-018, T-019 `done` + I-301..I-306 `done` |
| Phase 4: Scale and Sustainability | Months 19-24 | Community governance and long-term operating safeguards | T-022 `done` |

## Phase 1: Foundation (Months 1-6)

| ID | Task | Spec links | Status | Exit criteria |
|---|---|---|---|---|
| T-001 | Spec-first project scaffolding | `docs/specs/README.md`, `docs/specs/rfcs/0001-v1-moderation-api.md` | `done` | Templates, workflow, and DoD documented |
| T-002 | Public API contract and schemas | `docs/specs/api/openapi.yaml`, `docs/specs/schemas/*` | `done` | OpenAPI + JSON schemas aligned and contract check passing |
| T-003 | Moderation API vertical slice | `docs/specs/rfcs/0001-v1-moderation-api.md` | `done` | `/health` + `/v1/moderate` deterministic path implemented |
| T-004 | CI contract and test gates | `docs/specs/README.md` | `done` | CI runs contract check and test suite |
| T-005 | Lexicon repository abstraction | `docs/specs/adr/0001-lexicon-repository-fallback.md` | `done` | Postgres-first loader with file fallback and tests |
| T-006 | Lexicon release lifecycle governance | `docs/specs/adr/0002-lexicon-release-lifecycle.md`, `migrations/0002_lexicon_releases.sql` | `done` | Release states + activation flow + DB-backed active selection |
| T-007 | Release activation safety checks | `docs/specs/adr/0002-lexicon-release-lifecycle.md` | `done` | Empty releases cannot be activated; validation command implemented |
| T-008 | Lexicon ingest workflow (`create -> ingest -> validate -> activate`) | `docs/specs/rfcs/0001-v1-moderation-api.md` | `done` | Ingest command + tests for successful and invalid import cases |
| T-009 | Runtime metrics endpoint | `docs/master.md` (observability), `docs/specs/rfcs/0001-v1-moderation-api.md` | `done` | `/metrics` exposes action/status/error counters |
| T-010 | Contributor governance files | `docs/master.md`, `docs/specs/README.md` | `done` | `CONTRIBUTING.md`, PR template, and issue templates added |
| T-011 | Release audit trail for governance actions | `docs/specs/adr/0003-release-audit-trail.md`, `migrations/0003_lexicon_release_audit.sql` | `done` | Audit table + command hooks + list view + tests |
| T-012 | Policy configuration externalization | `docs/specs/adr/0004-policy-config-externalization.md`, `docs/specs/rfcs/0001-v1-moderation-api.md` | `done` | Move policy constants into versioned config with validation tests |
| T-013 | Metrics latency histogram | `docs/specs/rfcs/0001-v1-moderation-api.md`, `docs/specs/api/openapi.yaml`, `docs/specs/schemas/metrics-response.schema.json` | `done` | `/metrics` includes latency bucket counters for moderation decisions |
| T-014 | Standardized internal error contract (`HTTP_500`) | `docs/specs/rfcs/0001-v1-moderation-api.md`, `docs/specs/api/openapi.yaml` | `done` | Unexpected server errors return `ErrorResponse` with `request_id` and are documented in OpenAPI |
| T-015 | Latency SLO benchmark harness | `docs/master.md` (Sec. 3.1, Sec. 19), `docs/specs/rfcs/0001-v1-moderation-api.md` | `done` | Script produces p95 latency output for hot-path moderation and is documented |
| T-016 | Rate-limit header contract | `docs/specs/rfcs/0001-v1-moderation-api.md`, `docs/specs/api/openapi.yaml` | `done` | `/v1/moderate` responses include deterministic rate-limit headers and `Retry-After` on `429` |

## Phase 2: Intelligence Integration (Months 7-12)

| ID | Task | Spec links | Status | Exit criteria |
|---|---|---|---|---|
| T-017 | Async monitoring/update system spec | `docs/master.md` (Sec. 1.2, Sec. 3.2, Sec. 9.2), `docs/specs/rfcs/0002-async-monitoring-update-system.md` | `done` | RFC approved with deterministic pipeline states, SLA mapping, and acceptance criteria |
| T-020 | Security controls roadmap spec | `docs/master.md` (Sec. 11.2), `docs/specs/adr/0006-security-controls-roadmap.md` | `done` | ADR maps phased authn/authz/mTLS/RBAC/MFA controls with deadlines |
| T-021 | Data retention and privacy enforcement spec | `docs/master.md` (Sec. 12), `docs/specs/adr/0007-data-retention-privacy-controls.md` | `done` | ADR defines retention windows, deletion/legal-hold rules, and audit requirements |

## Phase 3: Election Readiness (Months 13-18)

| ID | Task | Spec links | Status | Exit criteria |
|---|---|---|---|---|
| T-018 | Electoral-phase policy mode spec | `docs/master.md` (Sec. 10.3), `docs/specs/adr/0005-electoral-phase-policy-modes.md` | `done` | ADR defines phase-mode data model, enforcement points, and rollout safety |
| T-019 | Appeals and transparency workflow spec | `docs/master.md` (Sec. 10.1, Sec. 21.1), `docs/specs/rfcs/0003-appeals-transparency-workflow.md` | `done` | RFC defines case reconstruction, appeal states, and audit exports |

## Phase 4: Scale and Sustainability (Months 19-24)

| ID | Task | Spec links | Status | Exit criteria |
|---|---|---|---|---|
| T-022 | Governance and community safeguards docs | `docs/master.md` (Sec. 17.2), `CODE_OF_CONDUCT.md`, `docs/specs/governance.md` | `done` | Governance charter + code of conduct added and referenced by CONTRIBUTING |

## Implementation Track (Post-Spec Approval)

### Phase 2 Implementation (Intelligence Integration)

| ID | Task | Spec links | Status | Exit criteria |
|---|---|---|---|---|
| I-201 | Async data model migrations | `docs/specs/rfcs/0002-async-monitoring-update-system.md` | `done` | Migrations create queue/event/cluster/proposal/review tables with indexes and audit fields |
| I-202 | Internal async schemas and contract checks | `docs/specs/rfcs/0002-async-monitoring-update-system.md` | `done` | Internal/admin JSON schemas added and validated in CI |
| I-203 | Queue state machine service | `docs/specs/rfcs/0002-async-monitoring-update-system.md` | `done` | Deterministic state transition engine implemented with invalid-transition guards |
| I-204 | Priority classifier + SLA timers | `docs/specs/rfcs/0002-async-monitoring-update-system.md`, `docs/master.md` (Sec. 3.2) | `done` | Queue prioritization and SLA breach counters/alerts implemented |
| I-205 | Proposal-to-release governance handoff | `docs/specs/rfcs/0002-async-monitoring-update-system.md`, `docs/specs/adr/0002-lexicon-release-lifecycle.md` | `done` | Approved proposals can create governed draft release artifacts |
| I-206 | Security stage S1 implementation (OAuth scopes for internal/admin APIs) | `docs/specs/adr/0006-security-controls-roadmap.md` | `done` | OAuth-based scope checks enforced for internal/admin endpoints |
| I-207 | Retention class tagging + legal hold primitives | `docs/specs/adr/0007-data-retention-privacy-controls.md` | `done` | Record-class taxonomy and legal-hold model enforced in write/delete paths |

### Phase 3 Implementation (Intelligence-Layer Execution)

| ID | Task | Spec links | Status | Exit criteria |
|---|---|---|---|---|
| I-301 | Real LID + span-level language routing | `docs/master.md` (Sec. 5.1, Sec. 7.3), `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md` | `done` | Span-level language routing implemented for Tier-1 languages with deterministic fallback and contract-safe response behavior |
| I-302 | Lexicon matcher v2 (boundary/phrase aware + normalization) | `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md`, `docs/specs/rfcs/0001-v1-moderation-api.md` | `in_progress` | Substring false positives eliminated; phrase-aware matching and evasion-resistance tests passing |
| I-303 | Redis hot triggers integration | `docs/master.md` (Sec. 5.2, Sec. 8.2), `docs/specs/adr/0001-lexicon-repository-fallback.md`, `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md` | `todo` | O(1) hot-trigger lookup path active with graceful fallback when Redis unavailable |
| I-304 | pgvector semantic matching on hot path | `docs/master.md` (Sec. 5.2, Sec. 8.2, Sec. 9.1), `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md` | `todo` | Runtime emits real `vector_match` evidence with bounded latency and deterministic policy integration |
| I-305 | Electoral phase modes runtime enforcement | `docs/specs/adr/0005-electoral-phase-policy-modes.md`, `docs/master.md` (Sec. 10.3), `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md` | `todo` | Effective phase-mode overrides enforced at runtime with validation and audit visibility |
| I-306 | Async monitoring pipeline worker activation | `docs/specs/rfcs/0002-async-monitoring-update-system.md`, `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md` | `todo` | Worker consumes queue and drives auditable state transitions through proposal generation handoff |
| I-307 | Staged package split to `core/router/lexicon/langpack/api` | `docs/master.md` (Sec. 17.1), `docs/specs/adr/0008-staged-package-boundary-migration.md` | `todo` | Package boundaries established with compatibility shims, dependency-direction statements per extraction PR, explicit rollback path per extraction PR, and no public contract break |

## Immediate Next (Execution Order)

1. I-301: real LID + span-level language routing.
2. I-302: lexicon matcher v2 (boundary/phrase aware + normalization).
3. I-303: Redis hot triggers integration.
4. I-304: pgvector semantic matching on hot path.

## Update Rule

When a task changes status:

1. Update this file in the same PR as the code/spec change.
2. Include task IDs in PR description.
3. Mark `done` only after tests and contract checks pass.
