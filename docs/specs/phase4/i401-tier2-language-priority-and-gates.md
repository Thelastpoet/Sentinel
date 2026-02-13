# I-401: Tier-2 Language Priority and Acceptance Gates

## 0. Document Control

- Status: Implemented and verified
- Effective date: 2026-02-12
- Scope: Priority order and acceptance/rollback gates for Tier-2 language-pack delivery
- Task linkage: `I-401` in `docs/specs/tasks.md`
- Source references: `docs/master.md` (Sec. 7.2, Sec. 13.2, Sec. 20), `docs/data-collection-strategy.md`

## 1. Decision Summary

Tier-2 implementation order for the current cycle is:

1. Luo
2. Kalenjin
3. Somali
4. Kamba

This order is now the default sequencing used by `I-407` delivery planning unless superseded by a later approved spec update.

## 2. Prioritization Method

Each candidate language was scored 1-5 on:

- Election risk exposure
- Expected traffic and code-switch surface
- Availability of trusted annotation and review partners
- Time-to-quality (expected speed to pass acceptance gates)

Deterministic tie-breakers:

1. Higher election-risk score wins.
2. If tied, higher partner-readiness score wins.
3. If still tied, lower expected delivery risk wins.

## 3. Ratified Priority Rationale

### 3.1 Luo (Priority 1)

- High electoral relevance and broad public discourse footprint.
- Strong partner/annotator feasibility in existing strategy notes.
- Good expected payoff for political-speech safety and bias reduction.

### 3.2 Kalenjin (Priority 2)

- High election-sensitivity contexts, especially in Rift Valley narratives.
- Strong risk-reduction value for incitement detection.
- Partner path identified in data-collection strategy.

### 3.3 Somali (Priority 3)

- Important for cross-border narrative and security-sensitive discourse.
- Requires targeted collection strategy; moderate partner-readiness.

### 3.4 Kamba (Priority 4)

- High utility and inclusion value, but lower immediate risk impact than top two.
- Scheduled after foundational Tier-2 process matures on first waves.

## 4. Acceptance Gates (Per Language Pack)

All gates must pass before enabling supervised enforcement for that language pack.

### 4.1 Data and Annotation Readiness

- Minimum 1,000 labeled evaluation samples per language.
- At least 20% of samples must be code-switched or mixed-context where applicable.
- Minimum 3 annotators per sample subset with adjudication path.
- Inter-annotator agreement (Krippendorff alpha) >= 0.67.

### 4.2 Quality Metrics

- High-severity harm classes (`ETHNIC_CONTEMPT`, `INCITEMENT_VIOLENCE`, `HARASSMENT_THREAT`):
  - F1 >= 0.80 (advisory gate)
  - F1 >= 0.86 (supervised enforcement gate)
- `BENIGN_POLITICAL_SPEECH` false-positive rate:
  - `BLOCK` false positives <= 0.5%
  - (`BLOCK` + `REVIEW`) false positives <= 3.0%
- Disparity check:
  - No subgroup/language-variant slice exceeds 1.5x overall false-positive rate.

### 4.3 Operational and Contract Safety

- No public API contract change (`scripts/check_contract.py` passes).
- Hot-path latency impact from new pack stays within:
  - Global P95 < 150ms
  - Added median latency <= 10ms for representative pack traffic.
- Full test suite must remain green.

## 5. Rollback Triggers

Any of the following triggers immediate rollback of the affected language pack version:

- `BLOCK` false-positive rate on benign political speech > 1.0% for two consecutive daily windows.
- High-severity class F1 drops below 0.75 after rollout.
- Material drift where subgroup disparity exceeds 2.0x overall false-positive rate.
- Repeated production incidents linked to language-pack normalization/tokenization defects.

Rollback path:

1. Revert active language-pack version to previous stable release.
2. Set affected pack posture to review-first until re-validation passes.
3. File incident record with metrics snapshot and remediation tasks.

## 6. Stage Alignment

This document defines pack-level gates; runtime stage behavior remains governed by `I-405`:

- Shadow: collect metrics only.
- Advisory: allow recommendation-only actions.
- Supervised enforcement: permitted only after all gates in Section 4 pass.

## 7. Execution Hand-off

- `I-406` must implement the metric pipeline needed to compute Section 4 and Section 5 thresholds.
- `I-407` must deliver packs in the ratified order from Section 1 and produce gate evidence for each pack release.
