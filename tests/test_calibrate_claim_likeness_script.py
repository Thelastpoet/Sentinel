from __future__ import annotations

import json
import subprocess
import sys


def test_calibrate_claim_likeness_script_writes_reports(tmp_path) -> None:
    output_json = tmp_path / "calibration.json"
    output_md = tmp_path / "calibration.md"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/calibrate_claim_likeness.py",
            "--dataset-path",
            "data/datasets/ml_calibration/v1/corpus.jsonl",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert output_json.exists()
    assert output_md.exists()
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert int(report["sample_count"]) >= 2000
    baseline = report["baseline"]["candidate"]
    selected = report["selected"]["candidate"]
    assert float(selected["medium_threshold"]) >= float(baseline["medium_threshold"])
    assert float(selected["high_threshold"]) >= float(baseline["high_threshold"])
