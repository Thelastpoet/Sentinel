# I-414: `model_version` Contract Clarity and Provenance Documentation

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-13
- Scope: Clarify `model_version` semantics across OpenAPI, RFC docs, and operations guidance
- Task linkage: `I-414` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 5.3, Sec. 8.3), `docs/specs/rfcs/0001-v1-moderation-api.md`, `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`, `docs/specs/adr/0009-model-runtime-interface-and-version-semantics.md`

## 1. Objective

Remove ambiguity that could imply `model_version` always refers to a trained ML model.

## 2. Required Behavior

1. Update OpenAPI schema descriptions for `model_version`.
2. Add explicit semantics in RFC docs and operator docs.
3. Define provenance requirements for values emitted in responses.
4. Preserve existing field name and response shape (no breaking change).

## 3. Acceptance Criteria

1. OpenAPI and schema docs clearly describe `model_version` as active inference artifact set identifier.
2. Contract checks remain green.
3. Regression tests confirm response shape is unchanged.

## 4. Implementation Notes

1. OpenAPI semantics:
   - `docs/specs/api/openapi.yaml` (`ModerationResponse.model_version`)
2. JSON schema semantics:
   - `docs/specs/schemas/moderation-response.schema.json`
   - `docs/specs/schemas/internal/appeal-request.schema.json` (`original_model_version`)
3. RFC clarification:
   - `docs/specs/rfcs/0001-v1-moderation-api.md`
4. Operations guidance:
   - `docs/operations.md` (`model_version` provenance section)
