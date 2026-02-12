# I-412: Disinformation Claim-Likeness Baseline Integration

## 0. Document Control

- Status: Ratified for implementation
- Effective date: 2026-02-12
- Scope: Deterministic claim-likeness signal for disinformation-risk handling
- Task linkage: `I-412` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 9.1, Sec. 21.2), `docs/specs/rfcs/0001-v1-moderation-api.md`

## 1. Objective

Implement a transparent, deterministic claim-likeness signal so disinfo handling is not solely lexicon/vector-match dependent.

## 2. Baseline Behavior

1. Produce a continuous claim-likeness score in `[0.0, 1.0]` from deterministic heuristics/features.
2. Derive categorical bands from fixed thresholds:
   - `low` (<0.40),
   - `medium` (>=0.40 and <0.70),
   - `high` (>=0.70).
3. Thresholds are versioned in policy config and cannot be changed without spec-linked update.
4. Feed signal into policy decisioning for `DISINFO_RISK` routing.
5. Preserve current safety posture:
   - no direct contract break;
   - no automatic escalation to `BLOCK` from claim-likeness alone.

## 3. Evidence and Explainability

1. Decision traces must include auditable reason codes for claim-likeness influence.
2. Heuristic/features used by baseline detector must be documented in:
   - `docs/specs/phase4/i412-claim-likeness-heuristics.md`
3. Behavior must be reproducible across runs for same input.

## 4. Acceptance Criteria

1. Claim-likeness baseline is integrated in hot path.
2. Unit/integration tests cover positive, negative, and ambiguous claim cases.
3. Benign political speech false-positive behavior is monitored with existing eval harness.
4. Public API response shape remains unchanged.
5. Score-to-band mapping and thresholds are validated by tests.
