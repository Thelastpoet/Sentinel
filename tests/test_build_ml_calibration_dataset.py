from __future__ import annotations

import json
import subprocess
import sys


def test_build_ml_calibration_dataset_script_outputs_required_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "ml_calibration_v1"
    agreement_report_path = tmp_path / "agreement.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_ml_calibration_dataset.py",
            "--output-dir",
            str(output_dir),
            "--agreement-report-path",
            str(agreement_report_path),
            "--sample-count",
            "2000",
            "--double-annotation-count",
            "120",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0

    corpus_path = output_dir / "corpus.jsonl"
    double_path = output_dir / "double_annotation_sample.jsonl"
    metadata_path = output_dir / "release_metadata.json"
    markdown_report_path = agreement_report_path.with_suffix(".md")

    assert corpus_path.exists()
    assert double_path.exists()
    assert metadata_path.exists()
    assert agreement_report_path.exists()
    assert markdown_report_path.exists()

    corpus_rows = corpus_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(corpus_rows) == 2000

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["sample_count"] == 2000
    assert metadata["tier1_coverage_complete"] is True
    assert metadata["meets_minimum_sample_count"] is True
