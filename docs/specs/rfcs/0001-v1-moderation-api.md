# RFC-0001: V1 Moderation API Vertical Slice

- Status: Approved
- Authors: Core maintainers
- Created: 2026-02-12
- Target milestone: Phase 1
- Related issues: TBD
- Supersedes: None

## 1. Summary

Define and ship the first production-shaped vertical slice for `POST /v1/moderate` with deterministic outputs, reason codes, and evidence traces.

## 2. Problem Statement

Without a stable contract and deterministic policy behavior, implementation will drift and external contributors will not have a reliable target for open-source collaboration.

## 3. Goals

- Provide a stable initial API contract for moderation requests.
- Guarantee deterministic response structure for every moderation result.
- Establish a contract-testable baseline before model complexity increases.

## 4. Non-Goals

- Full model-driven decision quality for all languages.
- End-to-end monitoring dashboard UI.
- Multi-tenant enterprise controls.

## 5. Proposed Behavior

Given a valid moderation request, the API returns:

- one action from `ALLOW`, `REVIEW`, `BLOCK`;
- one or more reason codes;
- evidence items tied to lexical/vector/model signals;
- language spans;
- artifact versions and latency.

## 6. API and Schema Impact

- OpenAPI path: `/v1/moderate`
- Request schema: `docs/specs/schemas/moderation-request.schema.json`
- Response schema: `docs/specs/schemas/moderation-response.schema.json`
- Backward compatibility: additive-only changes during `0.x`; breaking changes require RFC update and version bump.

## 7. Policy and Reason Codes

Initial reason-code families:

- `R_ETHNIC_*`
- `R_INCITE_*`
- `R_THREAT_*`
- `R_DOGWHISTLE_*`
- `R_DISINFO_*`
- `R_ALLOW_*`

## 8. Architecture and Data Impact

- API package for endpoint and validation
- Core package for policy decisioning
- Lexicon package for fast trigger checks (Postgres-backed with file fallback)
- Router package for language span output
- Database schema: `migrations/0001_lexicon_entries.sql`
- Release lifecycle schema: `migrations/0002_lexicon_releases.sql`
- Release audit schema: `migrations/0003_lexicon_release_audit.sql`
- Architecture decision: `docs/specs/adr/0001-lexicon-repository-fallback.md`
- Architecture decision: `docs/specs/adr/0002-lexicon-release-lifecycle.md`
- Architecture decision: `docs/specs/adr/0003-release-audit-trail.md`
- Architecture decision: `docs/specs/adr/0004-policy-config-externalization.md`

## 9. Security, Privacy, and Abuse Considerations

- API key auth required.
- Rate limiting responses expose deterministic headers (`X-RateLimit-*`, `Retry-After` on `429`).
- Request logging must avoid storing unnecessary personal metadata.
- Rate limiting required to mitigate probing and abuse.

## 10. Alternatives Considered

1. Start with model-only behavior: rejected due to nondeterministic operational risk.
2. Start with lexicon-only binary flag: rejected due to weak explainability and scalability.

## 11. Rollout Plan

- Stage 1: shadow outputs for internal validation.
- Stage 2: advisory responses for partner testing.
- Stage 3: supervised enforcement with sampling and audit.

## 12. Acceptance Criteria

1. Endpoint validates request against schema and rejects malformed payloads.
2. Endpoint returns response conforming to schema for all code paths.
3. Action always includes reason codes and evidence.
4. Version fields are always present.
5. Integration tests cover harmful, benign, and code-switched samples.
6. Unexpected server failures return structured `ErrorResponse` with `HTTP_500` and `request_id`.

## 13. Test Plan

- Unit tests for policy mapping and reason-code generation.
- Integration tests for endpoint behavior.
- Contract tests against OpenAPI and JSON schemas.
- Latency benchmark for P95 budget tracking.

## 14. Observability

- Structured logs with request IDs.
- Latency histogram by endpoint.
- Action distribution metrics (`ALLOW`, `REVIEW`, `BLOCK`).
- Alert when schema validation errors spike.
- `GET /metrics` exposes action/status counters, validation errors, and latency buckets.

## 15. Open Questions

1. Which initial reason-code set should be mandatory for v0.1.0?
2. What is the first default policy version string format?
