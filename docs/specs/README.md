# Sentinel Spec-Driven Development

This project uses a spec-first workflow. Code follows approved specs, not the other way around.

## 1. Source of Truth

Priority order for technical truth:

1. `docs/master.md` (product and system direction)
2. `docs/specs/rfcs/*.md` (feature-level behavioral specs)
3. `docs/specs/api/openapi.yaml` (public API contract)
4. `docs/specs/schemas/*.json` (payload and event schemas)
5. `docs/specs/adr/*.md` (architecture decisions)

If artifacts disagree, resolve by updating specs before implementation changes merge.

## 2. Development Workflow

1. Open issue with problem statement and goals.
2. Write or update an RFC in `docs/specs/rfcs/`.
3. Update API/schema specs if behavior or contract changes.
4. Add/update ADR if architecture tradeoffs are involved.
5. Implement code against approved spec.
6. Add tests mapped to acceptance criteria.
7. Verify checklist in `docs/specs/checklists/implementation.md`.

No feature PR is accepted without corresponding spec changes unless it is a pure refactor.

## 3. Pull Request Requirements

Every PR must include:

- Spec references (RFC ID, API section, schema file, ADR if relevant)
- Acceptance criteria mapping
- Backward compatibility statement
- Test evidence (unit/integration/contract)

## 4. Compatibility and Versioning

- Public API is semver-governed.
- Breaking API changes require:
  - RFC approval
  - migration notes
  - version bump and deprecation window
- Schema changes must be explicit about backward compatibility.

## 5. Testing Policy (Spec-Aligned)

- Contract tests validate `openapi.yaml` examples and constraints.
- `scripts/check_contract.py` must pass in CI to ensure spec artifacts remain consistent.
- Integration tests validate decision policy behavior and reason code emission.
- Regression tests are mandatory for production incidents and policy defects.

## 6. Definition of Done

A feature is done only when:

- spec approved
- implementation merged
- tests passing
- observability and reason-code traces present
- docs updated

## 7. Open Source Governance Notes

- Keep specs readable, deterministic, and reviewable by external contributors.
- Avoid hidden behavior; policy logic must be explicit in specs.
- Changes affecting moderation outcomes require at least two maintainer approvals.
- Governance baseline is documented in `docs/specs/governance.md`.

## 8. Task Tracking

- Track implementation progress in `docs/specs/tasks.md`.
- Every behavior-changing PR should update task status in that file.

## 9. Engineering Memory

- Record non-obvious implementation/testing lessons in `docs/specs/engineering-lessons.md`.
