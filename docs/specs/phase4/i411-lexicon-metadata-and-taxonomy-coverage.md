# I-411: Hate-Lex Metadata Completeness and Taxonomy Coverage Hardening

## 0. Document Control

- Status: Ratified for implementation
- Effective date: 2026-02-12
- Scope: Align lexicon artifact fields and baseline taxonomy coverage with master plan
- Task linkage: `I-411` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 6.1, Sec. 8.1), `data/lexicon_seed.json`

## 1. Objective

Close schema/data gaps between current seed artifacts and Hate-Lex requirements.

## 2. Required Metadata Fields

Each lexicon entry must include lifecycle metadata required by the master plan:

1. `first_seen`
2. `last_seen`
3. `status`
4. `change_history` (derived and aligned with `lexicon_release_audit` event pattern)

## 3. Taxonomy Coverage Requirement

Baseline seed must include at least one reachable production entry for each high-severity harm class:

1. `ETHNIC_CONTEMPT`
2. `INCITEMENT_VIOLENCE`
3. `HARASSMENT_THREAT`

Current baseline note:

- `ETHNIC_CONTEMPT` and `INCITEMENT_VIOLENCE` already have baseline coverage.
- `HARASSMENT_THREAT` must be added and validated in this task.

## 4. Migration and Compatibility Rules

1. Existing consumers must remain backward compatible during transition.
2. Repository loaders validate new fields while preserving graceful fallback behavior.
3. Contract checks/tests must fail when required fields or coverage are missing.

## 4.1 Backfill Timeline

1. Iteration A:
   - extend seed/schema and loaders for new metadata fields;
   - default missing legacy values with deterministic placeholders.
2. Iteration B:
   - backfill historical entries and release artifacts with resolved metadata values.
3. Iteration C:
   - enforce strict required-field validation and remove compatibility placeholders.

## 5. Acceptance Criteria

1. Seed/schema include required metadata fields.
2. Baseline coverage is explicitly validated for `ETHNIC_CONTEMPT`, `INCITEMENT_VIOLENCE`, and `HARASSMENT_THREAT`.
3. Ingest/release commands operate successfully with upgraded schema.
4. Public moderation response contract remains unchanged.
5. `change_history` derivation aligns with `lexicon_release_audit` semantics and is tested.
