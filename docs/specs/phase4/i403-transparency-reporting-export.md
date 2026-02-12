# I-403: Transparency Reporting and Export Surfaces

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Deterministic internal transparency reports and privacy-safe export records
- Task linkage: `I-403` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 10.1, Sec. 17.2), `docs/specs/rfcs/0003-appeals-transparency-workflow.md`

## 1. Objective

Provide deterministic transparency surfaces for appeals operations with strict RBAC and redaction controls:

1. aggregate reports for backlog/resolution outcomes;
2. exportable appeal records for transparency workflows;
3. default privacy protection for direct identifiers.

## 2. Runtime Surface

- Runtime module:
  - `src/sentinel_api/transparency.py`
- API endpoints:
  - `GET /admin/transparency/reports/appeals`
  - `GET /admin/transparency/exports/appeals`
- OAuth scopes:
  - `admin:transparency:read` for report access
  - `admin:transparency:export` for export access
  - `admin:transparency:identifiers` required when `include_identifiers=true`

## 3. Report Contract

Reports expose:

- total/open/resolved appeal counts;
- backlog over 72 hours (`backlog_over_72h`);
- status and resolution count maps;
- reversal rate and mean resolution hours.

Reports support optional `created_from` and `created_to` ISO-8601 filters.

## 4. Export Contract and Redaction

Export responses are deterministic and include:

- appeal status/action/reason-code payloads;
- artifact version snapshot (`model`, `lexicon`, `policy`, `pack`);
- transition count and timestamps.

Redaction behavior:

- default: `request_id` and `original_decision_id` are null;
- `include_identifiers=true` is only allowed with `admin:transparency:identifiers`.

## 5. Contract Artifacts

Internal schemas added:

- `docs/specs/schemas/internal/transparency-export-record.schema.json`
- `docs/specs/schemas/internal/transparency-appeals-report.schema.json`

`scripts/check_contract.py` validates schema presence and key enum constraints.

## 6. Verification Commands

```bash
python -m pytest -q tests/test_transparency_api.py tests/test_internal_admin_oauth.py
SENTINEL_INTEGRATION_DB_URL=postgresql://sentinel:sentinel@localhost:5432/sentinel python -m pytest -q tests/test_transparency_postgres_integration.py
python scripts/check_contract.py
python -m pytest -q
```
