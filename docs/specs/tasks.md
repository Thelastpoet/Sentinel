# Sentinel Spec Task Board

Last updated: 2026-02-13

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
| Phase 3: Election Readiness | Months 13-18 | Codify election-time controls, appeals, and transparency workflows | T-018, T-019 `done` + I-301..I-307 `done` |
| Phase 4: Scale and Sustainability | Months 19-24 | Tier-2 language expansion, partner integrations, evaluation/transparency operations, and ML readiness execution | Gate target: T-022 `done` + I-401..I-417 `done` |

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
| I-302 | Lexicon matcher v2 (boundary/phrase aware + normalization) | `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md`, `docs/specs/rfcs/0001-v1-moderation-api.md` | `done` | Substring false positives eliminated; phrase-aware matching and evasion-resistance tests passing |
| I-303 | Redis hot triggers integration | `docs/master.md` (Sec. 5.2, Sec. 8.2), `docs/specs/adr/0001-lexicon-repository-fallback.md`, `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md` | `done` | O(1) hot-trigger lookup path active with graceful fallback when Redis unavailable |
| I-304 | pgvector semantic matching on hot path | `docs/master.md` (Sec. 5.2, Sec. 8.2, Sec. 9.1), `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md` | `done` | Runtime emits real `vector_match` evidence with bounded latency and deterministic policy integration |
| I-305 | Electoral phase modes runtime enforcement | `docs/specs/adr/0005-electoral-phase-policy-modes.md`, `docs/master.md` (Sec. 10.3), `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md` | `done` | Effective phase-mode overrides enforced at runtime with validation and audit visibility |
| I-306 | Async monitoring pipeline worker activation | `docs/specs/rfcs/0002-async-monitoring-update-system.md`, `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md` | `done` | Worker consumes queue and drives auditable state transitions through proposal generation handoff |
| I-307 | Staged package split to `core/router/lexicon/langpack/api` | `docs/master.md` (Sec. 17.1), `docs/specs/adr/0008-staged-package-boundary-migration.md` | `done` | Package boundaries established with compatibility shims, dependency-direction statements per extraction PR, explicit rollback path per extraction PR, and no public contract break |

### Phase 4 Implementation (Scale and Sustainability)

| ID | Task | Spec links | Status | Exit criteria |
|---|---|---|---|---|
| I-401 | Tier-2 language priority order + acceptance gates | `docs/master.md` (Sec. 7.2, Sec. 13.2, Sec. 20), `docs/specs/phase4/i401-tier2-language-priority-and-gates.md` | `done` | Priority order for next Tier-2 packs is ratified and acceptance/rollback thresholds are documented |
| I-402 | Appeals workflow runtime implementation | `docs/master.md` (Sec. 10.1, Sec. 21.2), `docs/specs/rfcs/0003-appeals-transparency-workflow.md`, `docs/specs/phase4/i402-appeals-workflow-runtime.md` | `done` | Appeal state machine, case reconstruction, and adjudication actions are implemented with immutable audit trail |
| I-403 | Transparency reporting and export surfaces | `docs/master.md` (Sec. 10.1, Sec. 17.2), `docs/specs/rfcs/0003-appeals-transparency-workflow.md`, `docs/specs/phase4/i403-transparency-reporting-export.md` | `done` | Deterministic transparency export endpoints/reports ship with role-scoped access and redaction controls |
| I-404 | Partner fact-check connector framework | `docs/master.md` (Sec. 9.2, Sec. 14, Sec. 21.1), `docs/specs/phase4/i404-partner-factcheck-connector-framework.md` | `done` | Connector abstraction + retry/backoff/circuit-breaker behavior implemented with at least one reference connector |
| I-405 | Deployment-stage controls (shadow -> advisory -> supervised) | `docs/master.md` (Sec. 13.1, Sec. 16), `docs/specs/phase4/i405-deployment-stage-controls.md` | `done` | Runtime stage controls enforce mode-specific decision behavior with audit visibility and safe rollback toggles |
| I-406 | Per-language evaluation and bias-audit harness | `docs/master.md` (Sec. 13.2, Sec. 19), `docs/specs/phase4/i406-evaluation-bias-harness-baseline.md` | `done` | Eval pipeline reports precision/recall/F1 by language and harm class, plus false-positive and subgroup disparity metrics |
| I-407 | Tier-2 language-pack Wave 1 delivery | `docs/master.md` (Sec. 7.1, Sec. 7.2, Sec. 16), `docs/specs/phase4/i407-tier2-language-pack-wave1-delivery.md` | `done` | First Tier-2 language packs ship with versioned normalization/lexicon/calibration artifacts and pass defined eval gates |
| I-408 | Go-live readiness gate and release sign-off package | `docs/master.md` (Sec. 11, Sec. 13, Sec. 19, Sec. 20), `docs/specs/phase4/i408-go-live-readiness-gate.md` | `done` | Deterministic go/no-go gate, evidence bundle format, and role-based sign-off workflow are implemented and exercised with prerequisite quality/latency artifacts |
| I-409 | Tooling quality gates (`ruff` + `pyright`) | `docs/master.md` (Sec. 15), `docs/specs/phase4/i409-tooling-quality-gates.md` | `done` | Ruff/pyright configs exist, local commands are documented, and CI enforces both gates |
| I-410 | Latency SLO CI gate (`P95 < 150ms`) | `docs/master.md` (Sec. 3.1, Sec. 19), `docs/specs/phase4/i410-latency-slo-ci-gate.md` | `done` | Hot-path benchmark runs in CI with failing gate on p95 budget breach and artifact retention |
| I-411 | Hate-Lex metadata completeness + taxonomy coverage hardening | `docs/master.md` (Sec. 6.1, Sec. 8.1), `docs/specs/phase4/i411-lexicon-metadata-and-taxonomy-coverage.md` | `done` | Lexicon schema/seed include lifecycle metadata fields and baseline includes reachable `HARASSMENT_THREAT` coverage |
| I-412 | Disinformation claim-likeness baseline integration | `docs/master.md` (Sec. 9.1), `docs/specs/phase4/i412-disinfo-claim-likeness-baseline.md` | `done` | Deterministic claim-likeness signal is integrated into hot path with tests and no public contract break |
| I-413 | Model runtime interfaces and registry wiring | `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`, `docs/specs/phase4/i413-model-runtime-interface-and-registry.md`, `docs/specs/adr/0009-model-runtime-interface-and-version-semantics.md` | `todo` | Protocol-based adapters and registry are implemented with deterministic fallback and policy-engine decoupling |
| I-414 | `model_version` contract clarity and provenance docs | `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`, `docs/specs/phase4/i414-model-version-contract-clarity.md`, `docs/specs/adr/0009-model-runtime-interface-and-version-semantics.md` | `todo` | OpenAPI/RFC/ops docs explicitly define `model_version` semantics with no response-shape break |
| I-415 | Semantic embedding model selection gate | `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`, `docs/specs/phase4/i415-semantic-embedding-model-selection.md` | `todo` | Candidate embeddings are benchmarked vs baseline, one strategy is selected, and rollback is documented |
| I-416 | Multi-label inference integration (shadow-first) | `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`, `docs/specs/phase4/i416-multilabel-inference-shadow-mode.md` | `todo` | Classifier path runs in shadow/advisory mode with guardrails, latency budget compliance, and divergence observability |
| I-417 | Claim-likeness calibration and governance thresholds | `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`, `docs/specs/phase4/i417-claim-likeness-calibration-governance.md` | `todo` | Threshold updates are evidence-backed, audited, and governance-approved with per-language/subgroup reporting |

## Immediate Next (Execution Order)

1. `I-413`: establish model runtime interfaces and registry boundary.
2. `I-414`: clarify `model_version` contract semantics before model rollout.
3. `I-415`: run embedding bakeoff and ratify first production strategy.
4. `I-416`: integrate multi-label inference in shadow-first mode.
5. `I-417`: calibrate claim-likeness thresholds with governance sign-off.

## Execution Dependencies

1. `I-409` and `I-410` are hard prerequisites for `I-408`.
2. `I-408` cannot reach `done` while unresolved Section 20 decisions lack explicit launch disposition records.
3. `I-413` is prerequisite for `I-415` and `I-416`.
4. `I-414` is prerequisite for `I-416` go-live promotion beyond shadow.
5. `I-415` is prerequisite for `I-416` if classifier depends on semantic embedding provider.
6. `I-417` closes calibration/governance requirements after `I-416` shadow evidence is available.

## Update Rule

When a task changes status:

1. Update this file in the same PR as the code/spec change.
2. Include task IDs in PR description.
3. Mark `done` only after tests and contract checks pass.
