from __future__ import annotations

import json
import subprocess
import sys


def test_validate_ml_dataset_release_accepts_generated_dataset(tmp_path) -> None:
    output_dir = tmp_path / "dataset"
    agreement_report = tmp_path / "agreement.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/build_ml_calibration_dataset.py",
            "--output-dir",
            str(output_dir),
            "--agreement-report-path",
            str(agreement_report),
            "--sample-count",
            "2000",
            "--double-annotation-count",
            "120",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    metadata_path = output_dir / "release_metadata.json"

    validate = subprocess.run(
        [
            sys.executable,
            "scripts/validate_ml_dataset_release.py",
            "--corpus-path",
            str(output_dir / "corpus.jsonl"),
            "--double-annotation-path",
            str(output_dir / "double_annotation_sample.jsonl"),
            "--metadata-path",
            str(metadata_path),
            "--min-samples",
            "2000",
            "--min-binary-harmful-kappa",
            "0.6",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    report = json.loads(validate.stdout.strip())
    assert report["ok"] is True
    assert report["sample_count"] == 2000
