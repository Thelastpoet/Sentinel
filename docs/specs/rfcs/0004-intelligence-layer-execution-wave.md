# RFC-0004: Intelligence-Layer Execution Wave

- Status: Approved
- Authors: Core maintainers
- Created: 2026-02-12
- Target milestone: Phase 3 implementation kickoff
- Related issues: TBD
- Supersedes: None

## 1. Summary

Define the next implementation wave that turns Sentinel from governance-ready baseline into operational intelligence system, while preserving deterministic behavior and public API contract compatibility.

## 2. Problem Statement

Core scaffolding, governance controls, and async schema/state foundations are complete, but intelligence capabilities are still shallow in runtime behavior (language routing quality, lexical precision, semantic retrieval, and queue processing execution). This limits mission impact for Kenya election safety objectives.

## 3. Goals

- Implement intelligence-critical hot-path capabilities in dependency order.
- Keep `POST /v1/moderate` contract shape stable while improving evidence quality.
- Preserve deterministic policy behavior and measured latency budgets.
- Activate async queue consumption without coupling it to synchronous moderation path.

## 4. Non-Goals

- Rewriting core governance specifications already accepted.
- Building full UI workflows for appeals or monitoring.
- Introducing breaking public API changes in this wave.

## 5. Proposed Behavior

Delivery order (strict):

1. Real language identification and span-level routing (`I-301`) using a fastText
   baseline (`lid.176.bin`) plus deterministic fallback rules for low-confidence
   spans.
2. Lexicon matcher v2 with boundary/phrase-aware matching and normalization (`I-302`).
3. Redis-backed hot triggers with graceful fallback (`I-303`).
4. pgvector semantic matching and real `vector_match` evidence (`I-304`).
5. Electoral phase mode enforcement in runtime policy evaluation (`I-305`).
6. Async monitoring pipeline worker activation (`I-306`).

`I-307` (package split) is staged and non-blocking for intelligence behavior improvements.

## 6. API and Schema Impact

- Public API paths affected: none (shape-preserving).
- Response contract: unchanged required fields in `ModerationResponse`.
- Internal/admin behavior: additive runtime capabilities and observability fields as needed.
- Backward compatibility: mandatory for all tasks in this RFC.

## 7. Policy and Reason Codes

- Existing reason-code families remain valid.
- New evidence-generation paths (`vector_match`, improved lexical evidence) must map to existing reason-code semantics unless a new reason code is explicitly RFC-approved.
- Electoral phase modes must remain auditable in logs and policy versioning context.

## 8. Architecture and Data Impact

- Components touched: router, lexicon matcher, cache tier, vector retrieval, policy runtime, async worker.
- Data impact: additive indexes/tables only when required; existing migrations remain valid.
- Hot-path latency budget allocation (indicative, cumulative within P95 <150ms):
  - LID/span routing: <= 15ms
  - Lexicon matcher + normalization: <= 20ms
  - Redis hot-trigger lookup: <= 5ms
  - pgvector retrieval + scoring: <= 60ms
  - Policy merge/decision assembly: <= 20ms
  - Remaining budget reserved for framework overhead and jitter.
- Integration constraints:
  - hot-path remains deterministic and bounded by latency SLO;
  - async worker must not execute on request thread.

## 9. Security, Privacy, and Abuse Considerations

- Preserve OAuth scope enforcement for internal/admin APIs.
- Retention/legal-hold controls remain mandatory for new write/delete paths.
- Prevent adversarial prompt/evasion effects by deterministic normalization and explicit fallbacks.

## 10. Alternatives Considered

1. Continue governance-only progress before intelligence execution.
   - Rejected: delays mission-critical moderation quality improvements.
2. Ship all intelligence changes in one large PR wave.
   - Rejected: unacceptable regression and audit risk.

## 11. Rollout Plan

- Stage A: implement and verify `I-301` + `I-302`.
- Stage B: integrate Redis + pgvector (`I-303` + `I-304`) with latency gates.
- Stage C: enforce electoral modes and activate async worker (`I-305` + `I-306`).
- Stage D: execute staged package migration (`I-307`) without behavior break.

## 12. Acceptance Criteria

1. Each task (`I-301`..`I-306`) lands with explicit tests and no public contract break.
2. `POST /v1/moderate` still passes contract checks and existing schema requirements.
3. `I-301`: code-switched input yields multi-span `language_spans` with deterministic fallback behavior.
4. `I-302`: matcher eliminates known substring false positives (for example `skill` must not match `kill` trigger).
5. Hot-path latency remains under project SLO budget for benchmarked workloads.
6. Async worker transitions are auditable and conform to RFC-0002 state model.
7. Electoral phase mode changes are validated and observable.

## 13. Test Plan

- Unit tests:
  - LID/span routing behavior and fallback handling.
  - Lexicon matcher boundary and variant coverage.
  - Redis and vector retrieval adapters with failure fallbacks.
  - Electoral phase override logic.
  - Worker transition and retry logic.
- Integration tests:
  - End-to-end moderation paths with lexical + vector evidence.
  - Queue consume -> proposal handoff.
- Contract tests:
  - `scripts/check_contract.py` must remain green.
- Load/latency tests:
  - benchmark gate for P95 hot-path latency.

## 14. Observability

- Logs:
  - effective language spans and phase mode.
  - cache/vector path selected and fallback reason.
  - worker transition lineage (`request_id`, queue/proposal IDs).
- Metrics:
  - LID confidence/fallback counters.
  - Redis hit/miss and vector retrieval latency.
  - queue throughput and SLA breaches by priority.
- Alerts:
  - sustained fallback-only operation,
  - queue backlog/SLA breach thresholds.

## 15. Open Questions

1. Which initial embedding model and vector dimensionality should be standard for `I-304`?
2. For `I-301`, what confidence thresholds and tie-break rules should route spans to fallback mode?
3. For `I-307`, which package boundary should be extracted first after `core`?
