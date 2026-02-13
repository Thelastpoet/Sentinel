# I-307 Langpack Extraction (Step 3)

Date: 2026-02-12

## Dependency-Direction Statement

This step introduces explicit `sentinel_langpack` boundary.

Allowed direction in this step:

- `sentinel_api -> sentinel_core`
- `sentinel_api -> sentinel_router`
- `sentinel_api -> sentinel_lexicon`
- `sentinel_api -> sentinel_langpack`
- `sentinel_router -> sentinel_core`
- `sentinel_lexicon -> sentinel_core`
- `sentinel_langpack -> sentinel_core` (currently no direct dependency)

Disallowed direction:

- `sentinel_langpack -> sentinel_api`

## Compatibility Strategy

- Existing imports can continue through compatibility shim:
  - `sentinel_api.langpack` -> `sentinel_langpack.registry`
- Runtime now resolves `pack_versions` through `sentinel_langpack.registry.resolve_pack_versions(...)`.
- Public API contract remains unchanged.

## Rollback Path

If regressions occur:

1. Repoint `sentinel_api.policy` to use `config.pack_versions` directly.
2. Keep `sentinel_langpack` package present but unused.
3. Keep shim module intact to avoid import breaks.
4. Re-run full suite and contract checks before merge.
