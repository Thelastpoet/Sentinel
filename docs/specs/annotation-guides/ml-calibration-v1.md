# ML Annotation Guide v1 (Calibration Corpus)

Guide version: `ml-annotation-guide-v1`
Applies to: `data/datasets/ml_calibration/v1/corpus.jsonl`

## Scope

This guide defines labeling standards for claim-likeness and multi-label moderation calibration across Tier-1 languages (`en`, `sw`, `sh`).

## Labeling Rules

1. Assign at least one taxonomy label from:
   - `ETHNIC_CONTEMPT`
   - `INCITEMENT_VIOLENCE`
   - `HARASSMENT_THREAT`
   - `DOGWHISTLE_WATCH`
   - `DISINFO_RISK`
   - `BENIGN_POLITICAL_SPEECH`
2. Use `BENIGN_POLITICAL_SPEECH` only when content is political expression without harm intent or harmful assertions.
3. Allow multi-label assignment when signals overlap (for example disinformation + coded dog whistle).
4. Prefer `REVIEW`-oriented labels (`DOGWHISTLE_WATCH`, `DISINFO_RISK`) when intent is ambiguous.
5. Escalate to safety reviewer when annotator confidence is below 0.6.

## Reviewer Workflow

1. Primary annotation by annotator A.
2. Secondary annotation by annotator B on stratified sample.
3. Adjudication by reviewer for disagreements.
4. Final QA status set to `accepted` before release export.

Required record fields per sample:

- `id`, `text`, `language`, `labels`
- `is_benign_political`, `subgroup`
- `source`, `annotation_guide_version`, `qa_status`

## Quality Gates

1. Minimum corpus size: `>= 2000`.
2. Tier-1 language coverage required (`en`, `sw`, `sh`).
3. Inter-annotator agreement reported for each release:
   - exact label-set match rate
   - binary harmful Cohen's kappa
   - per-label kappa
4. No release without provenance metadata (`release_metadata.json`) and agreement report.

## Escalation Notes

- Do not auto-label uncertain political criticism as violence/incitement.
- Any potential chilling-effect examples must be tagged for reviewer audit.
