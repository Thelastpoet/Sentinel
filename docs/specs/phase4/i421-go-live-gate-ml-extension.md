# I-421: Go-Live Gate Extension for ML-Enforced Launch Mode

## 0. Document Control

- Status: Done
- Effective date: 2026-02-13
- Scope: Extend `I-408` go-live gate to support ML-enforced launch readiness decisions
- Task linkage: `I-421` in `docs/specs/tasks.md`
- Source references: `docs/specs/phase4/i408-go-live-readiness-gate.md`, `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`

## 1. Objective

Make explicit whether ML-wave tasks are optional or mandatory for a given launch profile.

## 2. Required Behavior

1. Define launch profiles:
   - `baseline_deterministic` (ML wave not required for launch),
   - `ml_enforced` (ML wave prerequisites required).
2. Extend go-live validator inputs to include selected launch profile.
3. For `ml_enforced`, require successful completion/evidence for `I-413`..`I-420`.
4. For `baseline_deterministic`, record explicit deferred disposition for ML-wave tasks.

## 3. Acceptance Criteria

1. `I-408` documentation and template bundle include launch-profile field.
2. Validator enforces profile-specific prerequisites.
3. Missing ML-wave evidence in `ml_enforced` profile returns `NO-GO`.
4. Profile decision and rationale are auditable in release bundle artifacts.
