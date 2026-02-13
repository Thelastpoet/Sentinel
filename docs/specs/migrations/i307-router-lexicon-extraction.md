# I-307 Router + Lexicon Extraction (Step 2)

Date: 2026-02-12

## Dependency-Direction Statement

This step introduces explicit router and lexicon package boundaries.

Allowed direction in this step:

- `sentinel_api -> sentinel_core`
- `sentinel_api -> sentinel_router`
- `sentinel_api -> sentinel_lexicon`
- `sentinel_router -> sentinel_core`
- `sentinel_lexicon -> sentinel_core`

Disallowed direction:

- `sentinel_router -> sentinel_api`
- `sentinel_lexicon -> sentinel_api`

## Compatibility Strategy

- Existing import paths remain valid through module-alias shims:
  - `sentinel_api.language_router` -> `sentinel_router.language_router`
  - `sentinel_api.lexicon_repository` -> `sentinel_lexicon.lexicon_repository`
  - `sentinel_api.lexicon` -> `sentinel_lexicon.lexicon`
  - `sentinel_api.hot_triggers` -> `sentinel_lexicon.hot_triggers`
  - `sentinel_api.vector_matcher` -> `sentinel_lexicon.vector_matcher`
- Runtime internals now import router/lexicon implementations directly from extracted packages.
- Public API and schema contracts remain unchanged.

## Rollback Path

If regressions occur:

1. Repoint `sentinel_api` internal imports back to in-package implementations.
2. Keep extracted packages present but unused.
3. Keep shim layer intact to avoid import breaks for tests/scripts.
4. Re-run full suite and contract checks before merge.
