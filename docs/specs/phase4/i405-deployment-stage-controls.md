# I-405: Deployment-Stage Runtime Controls

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Runtime stage controls for shadow, advisory, and supervised enforcement
- Task linkage: `I-405` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 13.1, Sec. 16), `docs/specs/rfcs/0001-v1-moderation-api.md` (Sec. 11)

## 1. Objective

Implement deterministic deployment stages so moderation behavior can be rolled out safely:

1. `shadow`
2. `advisory`
3. `supervised`

## 2. Runtime Control Surface

- Environment variable: `SENTINEL_DEPLOYMENT_STAGE`
- Allowed values: `shadow`, `advisory`, `supervised`
- Default when unset: `supervised`
- Invalid values: fail runtime resolution and startup validation

## 3. Stage Behavior

### 3.1 Supervised

- No action override (baseline enforcement behavior).

### 3.2 Advisory

- `BLOCK` decisions are downgraded to `REVIEW`.
- Existing labels/evidence are preserved.
- Reason code `R_STAGE_ADVISORY_BLOCK_DOWNGRADED` is appended.

### 3.3 Shadow

- Non-`ALLOW` decisions are converted to `ALLOW`.
- Existing labels/evidence are preserved for audit/analysis.
- Reason code `R_STAGE_SHADOW_NO_ENFORCE` is appended.

## 4. Audit Visibility

- Effective deployment stage is included in structured logs.
- `policy_version` includes a stage suffix for non-supervised stages:
  - `<version>#advisory`
  - `<version>#shadow`
- If electoral phase is active, suffix combines as:
  - `<version>@<phase>#<stage>`

## 5. Acceptance Criteria

1. Runtime resolves deployment stage deterministically from env/config/default.
2. Invalid stage values fail fast.
3. Stage behavior overrides are applied exactly as in Section 3.
4. Logs include `effective_deployment_stage`.
5. Tests cover default, invalid, stage-specific overrides, and policy-version suffixing.
