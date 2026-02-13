# Go-Live Evidence Bundle Template

Copy this directory to `docs/releases/go-live/<release-id>/` and fill every file with release-specific evidence.

Set `decision.json.launch_profile` explicitly:

1. `baseline_deterministic`
2. `ml_enforced`

Profile requirements:

1. `baseline_deterministic`:
   - include explicit Section 20 dispositions for `I-413`..`I-420` in `section20_dispositions.json`.
2. `ml_enforced`:
   - set `decision.json.ml_prerequisites.i413..i420` to `status=pass` with non-empty artifacts.
   - do not defer `I-413`..`I-420` as non-blockers/blockers in Section 20 dispositions.

Validator command:

```bash
python scripts/check_go_live_readiness.py --bundle-dir docs/releases/go-live/<release-id>
```
