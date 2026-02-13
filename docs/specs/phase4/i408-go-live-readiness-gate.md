# I-408: Go-Live Readiness Gate and Release Sign-Off Package

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Operational go/no-go gate for customer production launch
- Task linkage: `I-408` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 11, Sec. 13, Sec. 19, Sec. 20, Sec. 21)

## 1. Objective

Define a deterministic launch decision framework so "feature complete" is not confused with "customer production ready."

## 1.1 Prerequisites

`I-408` consumes artifacts produced by:

1. `I-409` (`ruff` + `pyright` CI quality gate outputs)
2. `I-410` (latency SLO CI gate output and retained benchmark artifacts)

## 2. Required Evidence Bundle

1. Reliability and latency report:
   - hot-path p95 under 150ms in representative environment;
   - error-rate and availability metrics for staging burn-in window.
2. Safety and quality report:
   - latest per-language eval and subgroup disparity metrics;
   - false-positive rates for benign political speech.
3. Security and controls report:
   - authz scope checks, rate-limit behavior, secrets handling, and audit-log integrity checks.
4. Legal and governance report:
   - retention/legal hold verification;
   - appeals/transparency operational drills completed.
5. Operational readiness report:
   - incident playbook drill summary;
   - rollback drill for policy, lexicon, and language-pack versions.

Evidence bundle storage location:

- `docs/releases/go-live/<release-id>/`
- must include machine-readable `decision.json` and referenced artifact files.

## 3. Go/No-Go Decision Rules

Launch is `GO` only when all required evidence artifacts are present and all gate criteria pass.

Launch is automatically `NO-GO` when any critical criterion fails, including:

- latency gate failure;
- unresolved critical security finding;
- unresolved critical fairness/safety regression;
- missing sign-off from required roles.

Section 20 decision handling (`docs/master.md`):

1. Every still-open decision must have an explicit launch disposition:
   - `accepted_for_launch` (with rationale and owner), or
   - `deferred_blocker` (automatic `NO-GO`), or
   - `deferred_non_blocker` (with mitigation, owner, and target resolution date).
2. Missing disposition records for Section 20 items is an automatic `NO-GO`.

## 4. Required Sign-Off Roles

1. Engineering lead
2. Safety/governance lead
3. Security lead
4. Legal/policy owner

Each sign-off record must include timestamp, evidence references, and decision rationale.

## 5. Acceptance Criteria

1. A machine-readable gate artifact format is defined and generated.
2. A release checklist command or script validates gate completeness.
3. Missing evidence or failed criteria returns non-zero status.
4. Go/no-go records are stored with immutable audit trail fields.
5. Gate run fails if prerequisite artifacts from `I-409` and `I-410` are absent.
6. Gate run fails when any Section 20 decision lacks disposition metadata.

## 6. Implementation Notes

1. Gate validator:
   - `scripts/check_go_live_readiness.py`
2. Operational command path:
   - `make go-live-check BUNDLE_DIR=docs/releases/go-live/<release-id>`
3. Template evidence bundle:
   - `docs/releases/go-live/template/`
   - includes `decision.json`, prerequisite artifacts, Section 20 dispositions,
     and role sign-off records.
4. Validator enforces:
   - required artifact presence;
   - prerequisite pass status for `i409` and `i410`;
   - required critical checks;
   - mandatory sign-off roles;
   - Section 20 disposition validity and blocker/no-blocker logic.
