# I-307 Core Extraction (Step 1)

Date: 2026-02-12

## Dependency-Direction Statement

This step establishes `sentinel_core` as the first extracted boundary with no internal package dependencies.

Allowed direction in this step:

- `sentinel_api -> sentinel_core`
- `scripts -> sentinel_core` (or compatibility shim)

Disallowed direction:

- `sentinel_core -> sentinel_api`

## Compatibility Strategy

- Existing import paths (`sentinel_api.models`, `sentinel_api.policy_config`, `sentinel_api.async_state_machine`) remain available as compatibility shims.
- Internal runtime modules have been switched to import core primitives directly from `sentinel_core`.
- No public API contract shape changes were introduced.

## Rollback Path

If regressions occur:

1. Repoint internal imports back to `sentinel_api.*` modules.
2. Keep `sentinel_core` package present but unused.
3. Retain shim files to avoid import breakage for existing tests/scripts.
4. Re-run full suite and contract checks before merging rollback.

