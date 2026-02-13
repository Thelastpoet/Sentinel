# ML Readiness Gap Analysis

Last updated: 2026-02-13

## Purpose

This document captures the gap between ML/AI capabilities described in the master plan and what currently exists in the codebase. It is intended to inform planning for model integration work ahead of the 2027 election readiness deadline.

## Master plan claims vs current implementation

| Capability | Master plan reference | Current implementation |
|---|---|---|
| Multi-label inference (single pass) | Sec. 5.2 hot path flow | Not implemented. Labels are derived from lexicon matches only. No classifier exists. |
| Embedding model for semantic similarity | Sec. 8.2, Sec. 20 (pending decision) | `hash-bow-v1`: deterministic 64-dim feature hashing using `blake2b`. No trained model. |
| Claim-likeness detection | Sec. 9.1 hot path | Deterministic heuristic baseline integrated in hot path. Emits `DISINFO_RISK` review signals (`R_DISINFO_CLAIM_LIKENESS_MEDIUM`/`HIGH`) when thresholds pass. No trained claim classifier yet. |
| Toxicity scoring | Sec. 5.3 output contract | Static float mapped per action in policy config (e.g. BLOCK=0.95, REVIEW=0.60, ALLOW=0.05). Not model-derived. |
| Language identification | Sec. 7.3 code-switching | fastText via optional env var. Only real ML model. Falls back to dictionary-based hints. |
| Model governance and deployment stages | Sec. 13.1 | Deployment stages (shadow/advisory/supervised) are implemented but operate on policy rules, not model outputs. |

## What exists today

### Lexicon-driven decision pipeline

The hot path in `src/sentinel_api/policy.py` follows a deterministic sequence:

1. Hot trigger lookup (Redis or in-memory)
2. Lexicon matcher (boundary-aware regex)
3. Vector similarity (hash-BOW, pgvector cosine distance, threshold 0.82)
4. Claim-likeness heuristic scoring for disinformation-oriented statements
5. Static policy rules (no-match action, deployment stage overrides)

Every label, reason code, and evidence item traces back to a lexicon entry, deterministic similarity heuristic, claim-likeness heuristic, or policy config value. No learned classifier currently participates in harm-label inference.

### Hash-BOW embeddings

`src/sentinel_lexicon/vector_matcher.py` implements `embed_text()`:

- Extracts tokens, bigrams, and trigrams with manual weights (1.0, 1.2, 0.5)
- Hashes each feature with `blake2b` into a 64-dimension signed vector
- Normalizes to unit length
- Stores and queries via pgvector (`vector(64)` column, IVFFlat index)

This is useful for near-duplicate and paraphrase detection but is not a semantic embedding model. It cannot capture meaning, context, or nuance beyond surface-level n-gram overlap.

Safety constraint: vector matches can only escalate to REVIEW, never BLOCK (enforced in `policy.py`).

### fastText language identification

`src/sentinel_router/language_router.py` optionally loads a fastText model:

- Requires `SENTINEL_LID_MODEL_PATH` env var pointing to a `.bin` file
- Requires the `fasttext` Python package to be installed
- Falls back to Swahili/Sheng hint dictionaries and a default language when unavailable
- Confidence threshold: 0.80 (configurable via `SENTINEL_LID_CONFIDENCE_THRESHOLD`)

This is the only trained model in the system. It is not bundled and must be provisioned separately.

## What is missing

### No model integration infrastructure

- **No model interface or protocol.** There is no abstract base class for embedding models, classifiers, or claim detectors. Swapping in a real model requires modifying concrete implementations directly.
- **No ML dependencies.** `pyproject.toml` has zero ML framework imports (no torch, transformers, sklearn, onnx, sentence-transformers).
- **No model loading/serving abstraction.** No model registry, weight management, or inference batching.
- **No feature extraction pipeline.** Text goes directly from raw input to lexicon matching. There is no shared tokenization or preprocessing step that a model could plug into.

### Remaining capability gaps

| Capability | Spec | Task ID | Status |
|---|---|---|---|
| Embedding model selection | `docs/specs/phase4/i415-semantic-embedding-model-selection.md` | I-415 | `todo` |
| Multi-label inference rollout (shadow-first) | `docs/specs/phase4/i416-multilabel-inference-shadow-mode.md` | I-416 | `todo` |
| Model runtime interface boundary | `docs/specs/phase4/i413-model-runtime-interface-and-registry.md` | I-413 | `todo` |
| `model_version` contract clarity | `docs/specs/phase4/i414-model-version-contract-clarity.md` | I-414 | `todo` |

### `model_version` is misleading

The `model_version` field in the moderation response (e.g. `"sentinel-multi-v2"`) is a static string from policy config. It exists for audit traceability but does not correspond to a loaded model artifact. Consumers of the API may interpret this as evidence of a trained model behind the system.

## Risk assessment

| Risk | Severity | Notes |
|---|---|---|
| Hash-BOW misses semantic meaning in coded rhetoric | High | Dog whistles and euphemisms that share no surface tokens with lexicon entries will not be caught by vector similarity. |
| No multi-label inference limits harm coverage | High | The system cannot detect harm categories absent from the lexicon. Novel rhetoric patterns require manual lexicon updates. |
| Claim-likeness baseline may over/under-trigger without calibration corpus | Medium | Current claim-likeness path is deterministic and threshold-based, so precision/recall depends on heuristic tuning and evaluation coverage. |
| LID accuracy degrades without fastText | Medium | Hint-based fallback may misroute spans in heavily code-switched text, leading to missed lexicon matches. |
| `model_version` creates false confidence for API consumers | Low | External integrators may assume ML-backed decisions when the system is purely rule-based. |

## Recommendations

1. **Define a model integration interface** before selecting specific models. A `Protocol` for embedding and classification would allow the hash-BOW and any future model to be swapped without modifying the policy engine.

2. **Calibrate claim-likeness thresholds** with labeled data and publish per-language false-positive/false-negative slices so the heuristic baseline can be tuned with evidence.

3. **Evaluate real embedding models** against the hash-BOW baseline. Sentence-transformers or multilingual-e5 models would capture semantic similarity that hash-BOW cannot, but add latency and infrastructure requirements that must be measured against the P95 < 150ms budget.

4. **Clarify `model_version` semantics** in the API documentation and OpenAPI spec. Either rename it to `system_version` or document that it does not imply a trained ML model.

5. **Add ML dependencies as optional extras** in `pyproject.toml` (e.g. `pip install sentinel[ml]`) to keep the base install lightweight while enabling model-backed components.

## Related documents

- Master plan: `docs/master.md` (Sec. 5.2, 8.2, 9.1, 13.1, 20)
- ML execution RFC: `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`
- Model interface ADR: `docs/specs/adr/0009-model-runtime-interface-and-version-semantics.md`
- Claim-likeness spec: `docs/specs/phase4/i412-disinfo-claim-likeness-baseline.md`
- Deployment stages: `docs/specs/phase4/i405-deployment-stage-controls.md`
- Evaluation harness: `docs/specs/phase4/i406-evaluation-bias-harness-baseline.md`
- Task board: `docs/specs/tasks.md`
