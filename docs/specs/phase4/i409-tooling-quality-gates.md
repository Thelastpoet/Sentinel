# I-409: Tooling Quality Gates (`ruff` + `pyright`)

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Static quality enforcement aligned with technology stack commitments
- Task linkage: `I-409` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 15, Sec. 19)

## 1. Objective

Enforce deterministic lint and type-check gates in local workflow and CI.

## 2. Required Deliverables

1. Repository configuration for:
   - `ruff` (lint rules, exclusions, line-length policy)
   - `pyright` (type-check mode, include/exclude paths)
2. Documented local commands in `README.md` and/or `Makefile`.
3. CI workflow steps that fail on lint/type errors.
4. Tool version governance strategy:
   - tooling is declared centrally in project dependency/config files;
   - CI and local commands use the same installation path and commands;
   - upgrades are applied deliberately via normal dependency update PRs.

## 2.1 Type-Check Mode Decision

Baseline mode is `standard` for initial enforcement.

Migration path to stricter mode:

1. start at `standard` with zero-error policy in scoped paths;
2. tighten package-by-package to `strict` with explicit milestone PRs;
3. document completed strict-coverage scope in this spec when adopted.

## 3. Minimum Enforcement Scope

1. `src/`
2. `scripts/`
3. `tests/` (at minimum for linting; typed checks as explicitly configured)

## 4. Acceptance Criteria

1. `ruff` and `pyright` run successfully on a clean branch.
2. CI fails when either gate fails.
3. Gate behavior is reproducible locally with documented commands.
4. Existing test and contract checks remain green.
5. Tooling versions are centrally governed and consumed consistently in CI and local workflow.
6. `pyright` mode is explicitly declared in config and reflected in CI invocation.

## 5. Implementation Notes

1. Tool configuration is in:
   - `pyproject.toml` for `ruff` target version/line-length/rule set;
   - `pyrightconfig.json` for `pyright` `typeCheckingMode = "standard"` with scoped includes.
2. CI enforcement is in `.github/workflows/ci.yml`:
   - `python -m ruff check src scripts tests`
   - `python -m pyright src scripts`
3. Local reproducibility paths:
   - `make lint`
   - `make typecheck`
