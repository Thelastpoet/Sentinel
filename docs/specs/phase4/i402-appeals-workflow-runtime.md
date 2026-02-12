# I-402: Appeals Workflow Runtime Implementation

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Internal appeals lifecycle runtime, case reconstruction, and adjudication actions
- Task linkage: `I-402` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 10.1, Sec. 21.2), `docs/specs/rfcs/0003-appeals-transparency-workflow.md`

## 1. Objective

Implement the internal runtime for the approved appeals workflow:

1. create appeal records linked to original moderation artifacts;
2. enforce deterministic lifecycle transitions;
3. provide point-in-time case reconstruction with immutable audit events.

## 2. Runtime Surface

- Data layer:
  - `migrations/0008_appeals_core.sql`
  - `migrations/0009_appeals_original_decision_id_backfill.sql`
- State machine:
  - `sentinel_core.async_state_machine.validate_appeal_transition(...)`
- API:
  - `POST /admin/appeals`
  - `GET /admin/appeals`
  - `POST /admin/appeals/{appeal_id}/transition`
  - `GET /admin/appeals/{appeal_id}/reconstruct`
- Authorization scopes:
  - `admin:appeal:write` for create/transition
  - `admin:appeal:read` for list/reconstruct

## 3. Lifecycle Rules

Allowed transitions are:

- `submitted -> triaged | rejected_invalid`
- `triaged -> in_review | rejected_invalid`
- `in_review -> resolved_upheld | resolved_reversed | resolved_modified`
- terminal states have no outbound transitions.

Resolution guardrails:

- resolution payload is only valid for resolved states;
- `resolved_reversed` and `resolved_modified` require replacement reason codes;
- `resolved_upheld` defaults resolution reason codes to original reason codes when omitted.

## 4. Reconstruction Contract

Reconstruction responses include:

- stored original artifact versions (`model`, `lexicon`, `policy`, `pack`);
- original reason codes and final resolution payload;
- full chronological transition timeline (`appeal_audit`).

## 5. Contract Artifacts

Internal schemas added:

- `docs/specs/schemas/internal/appeal-request.schema.json`
- `docs/specs/schemas/internal/appeal-state-transition.schema.json`
- `docs/specs/schemas/internal/appeal-resolution.schema.json`

`scripts/check_contract.py` validates schema presence and key enum constraints.

## 6. Verification Commands

Run after migrations:

```bash
python scripts/apply_migrations.py --database-url postgresql://sentinel:sentinel@localhost:5432/sentinel
python -m pytest -q tests/test_async_state_machine.py tests/test_admin_appeals_api.py tests/test_internal_admin_oauth.py
SENTINEL_INTEGRATION_DB_URL=postgresql://sentinel:sentinel@localhost:5432/sentinel python -m pytest -q tests/test_appeals_schema_integration.py tests/test_appeals_postgres_integration.py
python scripts/check_contract.py
```
