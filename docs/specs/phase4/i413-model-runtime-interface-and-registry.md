# I-413: Model Runtime Interfaces and Registry Wiring

## 0. Document Control

- Status: Ratified for implementation
- Effective date: 2026-02-13
- Scope: Protocol-based model integration boundary for embedding/classifier/claim modules
- Task linkage: `I-413` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 5.2, Sec. 8.3), `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`, `docs/specs/adr/0009-model-runtime-interface-and-version-semantics.md`

## 1. Objective

Define and implement explicit model interfaces so model-backed and heuristic-backed components can be swapped without policy-engine rewrites.

## 2. Required Behavior

1. Introduce interfaces/protocols for:
   - embedding provider,
   - multi-label classifier,
   - claim-likeness scorer.
2. Add registry/resolver wiring used by policy runtime.
3. Preserve deterministic fallback when model providers are unavailable.
4. Keep moderation API contract unchanged.

## 3. Acceptance Criteria

1. Policy code depends on interfaces, not concrete model classes.
2. At least one deterministic baseline adapter is registered per interface.
3. Unit tests cover selection, fallback, and error handling paths.
4. `ruff`, `pyright`, `pytest`, and `scripts/check_contract.py` remain green.
