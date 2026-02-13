# I-412 Claim-Likeness Heuristics (Baseline)

## Purpose

Records deterministic features and scoring logic used by the `I-412` disinformation claim-likeness baseline.

## Feature Extraction Rules

Text is normalized with NFKC and lower-cased. Tokens are extracted with
`[0-9A-Za-zÀ-ÖØ-öø-ÿ']+`.

Features:

1. `election_anchor` (+0.35): token intersects election anchors
   (`election`, `vote`, `ballot`, `tally`, `results`, `iebc`, etc.).
2. `assertive_claim_term` (+0.25): token intersects assertive terms
   (`is`, `were`, `has`, `rigged`, `manipulated`, `falsified`, etc.).
3. `disinfo_narrative_term` (+0.20): token intersects narrative-risk terms
   (`rigged`, `manipulated`, `falsified`, `stolen`, `fraud`, `fake`).
4. `numeric_reference` (+0.10): at least one numeric token.
5. `long_form_statement` (+0.10): token count >= 8.
6. `question_penalty` (-0.20): input contains `?`.
7. `hedging_penalty` (-0.20): token intersects hedging set
   (`alleged`, `rumor`, `unconfirmed`, `maybe`, `might`, etc.).

## Score Normalization

Raw score is clamped to `[0.0, 1.0]`.

## Band Mapping

Thresholds come from policy config (`claim_likeness`):

1. `low`: score < `medium_threshold` (default `0.40`)
2. `medium`: `medium_threshold` <= score < `high_threshold` (default `0.70`)
3. `high`: score >= `high_threshold`

Validation rule: `medium_threshold < high_threshold`.

## Known Failure Modes and Conservative Handling

1. Questions and hedged language can still produce medium scores on strongly
   disinfo-like wording; these route to `REVIEW`, never `BLOCK`.
2. Claim-likeness cannot trigger `BLOCK` without independent policy evidence.
3. If election anchors are absent and policy requires anchors, score does not
   trigger disinfo routing.

## Versioning and Change Control

1. Weights and token sets are treated as policy-linked behavior and must be
   changed only via spec-linked PR.
2. Threshold changes require updating:
   - `config/policy/default.json`
   - `docs/specs/phase4/i412-disinfo-claim-likeness-baseline.md`
   - this heuristics file.

## Linkage

- Parent spec: `docs/specs/phase4/i412-disinfo-claim-likeness-baseline.md`
- Task: `I-412` in `docs/specs/tasks.md`
