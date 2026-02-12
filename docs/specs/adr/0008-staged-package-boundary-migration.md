# ADR-0008: Staged Package Boundary Migration to `core/router/lexicon/langpack/api`

- Status: Proposed
- Date: 2026-02-12
- Decision makers: Core maintainers
- Related RFCs: `docs/specs/rfcs/0001-v1-moderation-api.md`, `docs/specs/rfcs/0004-intelligence-layer-execution-wave.md`

## Context

`docs/master.md` defines a monorepo structure with internal packages (`core`, `router`, `lexicon`, `langpack`, `api`). Current implementation is intentionally compact under `src/sentinel_api/`. As intelligence-layer complexity grows, explicit package boundaries are needed to reduce coupling and improve test and ownership clarity.

## Decision

Adopt a staged migration strategy from single package to explicit package boundaries, without breaking runtime behavior or public API contracts.

Staging:

1. Extract `core` first (shared types/config/policy primitives with no internal dependencies).
2. Define and enforce allowed dependency directions.
3. Extract packages incrementally with compatibility import shims.
4. Move tests alongside package boundaries.
5. Remove shims only after full migration and stable releases.

Target dependency direction:

```text
api -> core
api -> router
api -> lexicon
api -> langpack

router -> core
lexicon -> core
langpack -> core

core -> (no internal package dependencies)
```

## Rationale

- Preserves delivery velocity for intelligence features while enabling cleaner architecture.
- Avoids high-risk big-bang refactor.
- Supports open-source contributor onboarding by clear module ownership.

## Consequences

- Positive:
  - Stronger separation of concerns and maintainability.
  - Clear extension paths for language packs and model adapters.
- Negative:
  - Temporary compatibility-layer overhead.
  - Additional migration planning and CI guard requirements.
- Neutral:
  - Runtime behavior should remain contract-equivalent during migration.

## Alternatives Considered

1. Keep single package indefinitely.
   - Rejected: rising complexity and cross-module coupling risk.
2. Big-bang package split in one milestone.
   - Rejected: high regression risk during active intelligence delivery.

## Implementation Notes

- Tracked as `I-307` in `docs/specs/tasks.md`.
- Target packaging mechanism is `uv` workspace mode with `[tool.uv.workspace]` members
  for each internal package (`core`, `router`, `lexicon`, `langpack`, `api`).
- Migration must be contract-safe (`scripts/check_contract.py` and full tests green).
- Recommended extraction sequence:
  1. `core`
  2. `router` and `lexicon` (in either order, both depending only on `core`)
  3. `langpack`
  4. `api`
- Each extraction PR must include:
  - dependency-direction statement,
  - compatibility strategy,
  - rollback path.
