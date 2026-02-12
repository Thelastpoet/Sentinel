# RFC-0003: Appeals and Transparency Workflow

- Status: Approved
- Authors: Core maintainers
- Created: 2026-02-12
- Target milestone: Phase 3
- Related issues: TBD
- Supersedes: None

## 1. Summary

Specify a deterministic appeals and transparency workflow for moderation decisions, including case reconstruction, review states, and exportable audit artifacts.

## 2. Problem Statement

`docs/master.md` commits to appeals and transparency workflows, but the current spec set does not define how decisions are challenged, reviewed, and resolved with traceable evidence.

## 3. Goals

- Define an auditable appeal lifecycle and ownership model.
- Ensure point-in-time reconstruction for every appealed decision.
- Produce privacy-safe transparency exports with consistent structure.

## 4. Non-Goals

- Full public-facing appeals portal UI.
- Fully automated policy reversal without human review.

## 5. Proposed Behavior

Appeal lifecycle states:

| State | Allowed next states |
|---|---|
| `submitted` | `triaged`, `rejected_invalid` |
| `triaged` | `in_review`, `rejected_invalid` |
| `in_review` | `resolved_upheld`, `resolved_reversed`, `resolved_modified` |
| `rejected_invalid` | terminal |
| `resolved_upheld` | terminal |
| `resolved_reversed` | terminal |
| `resolved_modified` | terminal |

Mandatory appeal record fields:

- appeal ID, original decision ID, request ID
- original and effective artifact versions (`model`, `lexicon`, `policy`, `pack`)
- reviewer actor, rationale, and timestamps for each transition
- final resolution code and rationale

## 6. API and Schema Impact

- New internal/admin endpoints:
  - create appeal
  - list/filter appeals
  - transition appeal state
  - export transparency records
- New schemas:
  - `appeal-request`
  - `appeal-state-transition`
  - `appeal-resolution`
  - `transparency-export-record`
- Backward compatibility:
  - no breaking changes to `/v1/moderate`

## 7. Policy and Reason Codes

- Appeal records must preserve original reason codes and evidence.
- Reversed/modified outcomes require explicit replacement reason codes.
- Resolution cannot remove audit linkage to original decision artifacts.

## 8. Architecture and Data Impact

- Add appeal tables linked to decision records and audit logs.
- Require point-in-time artifact lookup for reconstructed context.
- Add export job for periodic transparency snapshots.

## 9. Security, Privacy, and Abuse Considerations

- Strict RBAC for appeal review and export actions.
- Full audit logging for all appeal state transitions.
- Transparency exports must exclude direct identifiers unless legally required.

## 10. Alternatives Considered

1. No formal appeal flow in v1.
   - Rejected: conflicts with governance commitments.
2. Manual appeals in external tools.
   - Rejected: poor traceability and inconsistent outcomes.

## 11. Rollout Plan

- Stage 1: internal-only appeal workflow and storage.
- Stage 2: partner-facing access for approved channels.
- Stage 3: standardized transparency export cadence.

## 12. Acceptance Criteria

1. Appeal state transitions follow defined lifecycle and reject invalid transitions.
2. Every appeal can reconstruct original decision context at point-in-time.
3. Resolution outcomes (`upheld`/`reversed`/`modified`) are explicit and auditable.
4. Transparency exports are generated in privacy-safe format.

## 13. Test Plan

- Unit tests:
  - appeal state machine and transition validation
  - resolution payload validation
- Integration tests:
  - decision -> appeal linkage and artifact reconstruction
  - review transition audit trail
- Contract tests:
  - internal/admin appeal schemas
  - export record schema validation
- Load tests:
  - appeal backlog behavior and resolution SLA monitoring

## 14. Observability

- Logs: appeal create/transition/export events with trace IDs.
- Metrics: open appeals by state, resolution latency, reversal rate.
- Alerts: appeal SLA breaches and unresolved backlog growth.

## 15. Acceptance-to-Verification Mapping

| Acceptance criterion | Verification |
|---|---|
| AC-1 Valid lifecycle enforcement | Unit tests for state machine + integration invalid-transition test |
| AC-2 Point-in-time reconstruction | Integration test asserting artifact version rehydration |
| AC-3 Auditable outcomes | Integration test for transition + reviewer audit fields |
| AC-4 Privacy-safe exports | Contract/schema tests + export privacy checks |
