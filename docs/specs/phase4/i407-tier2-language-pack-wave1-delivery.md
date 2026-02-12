# I-407: Tier-2 Language-Pack Wave 1 Delivery

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Wave 1 delivery for Tier-2 language packs in ratified order
- Task linkage: `I-407` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 7.1, Sec. 7.2, Sec. 16), `docs/specs/phase4/i401-tier2-language-priority-and-gates.md`

## 1. Objective

Deliver the first Tier-2 pack wave with concrete artifacts and deterministic gate checks:

1. versioned pack artifacts for Luo and Kalenjin;
2. per-pack evaluation datasets and release-gate verification;
3. machine-verifiable pass/fail output for governance review.

## 2. Wave 1 Scope

Ratified order from `I-401` for this wave:

1. Luo (`pack-luo-0.1`)
2. Kalenjin (`pack-kalenjin-0.1`)

Artifacts are tracked in `data/langpacks/registry.json`.

## 3. Delivered Artifacts

For each pack:

- `normalization.json` (deterministic token normalization rules)
- `lexicon.json` (pack-local harmful-term set with label/action/severity)
- `calibration.json` (gate thresholds and target stage)

Paths:

- `data/langpacks/pack-luo-0.1/`
- `data/langpacks/pack-kalenjin-0.1/`

## 4. Gate Evaluation Surface

- Registry + gate engine: `src/sentinel_langpack/wave1.py`
- Verification CLI: `scripts/verify_tier2_wave1.py`
- Eval sets:
  - `data/eval/tier2/pack-luo-0.1.eval.jsonl`
  - `data/eval/tier2/pack-kalenjin-0.1.eval.jsonl`

Gate checks enforce:

- sample count and code-switch ratio readiness;
- annotator and agreement thresholds;
- high-severity class F1 thresholds for advisory/supervised stage targets;
- benign false-positive and subgroup disparity limits.

## 5. Verification Commands

```bash
python -m pytest -q tests/test_langpack_registry.py tests/test_eval_harness.py tests/test_langpack_wave1.py
python scripts/verify_tier2_wave1.py --registry-path data/langpacks/registry.json --pretty
python scripts/check_contract.py
python -m pytest -q
```
