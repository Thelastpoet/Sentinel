# I-409: Tooling Quality Gates (`ruff` + `pyright`)

## 0. Document Control

- Status: Ratified for implementation
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
4. Tool version pinning strategy:
   - versions pinned in dependency/config files;
   - CI and local commands use the same pinned versions.

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
5. Pinned tool versions are used consistently in CI and local developer workflow.
6. `pyright` mode is explicitly declared in config and reflected in CI invocation.
