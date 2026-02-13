# I-420: Optional ML Dependency Packaging (`sentinel[ml]`)

## 0. Document Control

- Status: Done
- Effective date: 2026-02-13
- Scope: Add optional ML dependency extras for embedding/classifier integrations
- Task linkage: `I-420` in `docs/specs/tasks.md`
- Source references: `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`, `docs/ml-readiness-gap-analysis.md`

## 1. Objective

Enable ML-capable runtime paths without forcing heavy dependencies into base installs.

## 2. Required Behavior

1. Add `[project.optional-dependencies].ml` in `pyproject.toml`.
2. Include model-runtime dependencies required by selected `I-415`/`I-416` strategy.
3. Document install commands and runtime prerequisites.
4. Keep base `pip install .` path unchanged for deterministic baseline users.

## 3. Acceptance Criteria

1. `pip install .[ml]` succeeds in clean environment.
2. Base install remains functional without ML extras.
3. CI includes one ML-extra install smoke path.
4. Documentation clearly separates base vs ML-enabled runtime expectations.
