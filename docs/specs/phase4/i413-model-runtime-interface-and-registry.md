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

Protocol contract (normative):

1. `EmbeddingProvider`:
   - `name: str`, `version: str`, `dimension: int`
   - `embed(text: str, *, timeout_ms: int) -> list[float] | None`
   - returns `None` on timeout/error/unavailable (never raises to request path).
2. `MultiLabelClassifier`:
   - `name: str`, `version: str`, `labels: tuple[str, ...]`
   - `predict(text: str, *, timeout_ms: int) -> list[tuple[str, float]] | None`
   - scores are `[0,1]`; unknown labels must be dropped before policy merge.
3. `ClaimScorer`:
   - `name: str`, `version: str`
   - `score(text: str, *, timeout_ms: int) -> tuple[float, str] | None`
   - tuple is `(score, band)` where `band in {"low","medium","high"}`.
4. Error contract:
   - providers must not throw uncaught exceptions into policy runtime;
   - runtime logs provider failures and falls back to deterministic baseline.
5. Registry contract:
   - selected provider IDs come from config/env;
   - missing/invalid provider IDs must route to baseline provider.

## 3. Acceptance Criteria

1. Policy code depends on interfaces, not concrete model classes.
2. At least one deterministic baseline adapter is registered per interface.
3. Unit tests cover selection, fallback, and error handling paths.
4. `ruff`, `pyright`, `pytest`, and `scripts/check_contract.py` remain green.
5. Protocol signature tests enforce return types and timeout/failure fallback behavior.
