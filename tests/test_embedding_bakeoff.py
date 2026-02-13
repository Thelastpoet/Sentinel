from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel_core.embedding_bakeoff import run_embedding_bakeoff


def _write_eval(path: Path) -> None:
    rows = [
        {
            "id": "s1",
            "text": "They should kill them now.",
            "language": "en",
            "labels": ["INCITEMENT_VIOLENCE"],
            "is_benign_political": False,
        },
        {
            "id": "s2",
            "text": "Election was rigged yesterday.",
            "language": "en",
            "labels": ["DISINFO_RISK"],
            "is_benign_political": False,
        },
        {
            "id": "s3",
            "text": "Discuss policy peacefully.",
            "language": "en",
            "labels": ["BENIGN_POLITICAL_SPEECH"],
            "is_benign_political": True,
        },
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _write_lexicon(path: Path) -> None:
    payload = {
        "version": "test-v1",
        "entries": [
            {
                "term": "kill",
                "action": "BLOCK",
                "label": "INCITEMENT_VIOLENCE",
                "reason_code": "R_INCITE_CALL_TO_HARM",
                "severity": 3,
                "lang": "en",
                "status": "active",
            },
            {
                "term": "rigged",
                "action": "REVIEW",
                "label": "DISINFO_RISK",
                "reason_code": "R_DISINFO_NARRATIVE_SIMILARITY",
                "severity": 1,
                "lang": "en",
                "status": "active",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_embedding_bakeoff_returns_selection(tmp_path: Path) -> None:
    eval_path = tmp_path / "eval.jsonl"
    lexicon_path = tmp_path / "lexicon.json"
    _write_eval(eval_path)
    _write_lexicon(lexicon_path)

    report = run_embedding_bakeoff(
        input_path=eval_path,
        lexicon_path=lexicon_path,
        similarity_threshold=0.2,
        enable_optional_models=False,
    )
    reports = report["reports"]
    assert isinstance(reports, list)
    baseline = next(item for item in reports if item.get("candidate_id") == "hash-bow-v1")
    assert baseline["available"] is True
    assert "weighted_f1" in baseline
    assert "benign_fp_rate" in baseline
    selected_candidate_id = report["selected_candidate_id"]
    available_ids = {item["candidate_id"] for item in reports if item.get("available") is True}
    assert selected_candidate_id in available_ids
    if selected_candidate_id != "hash-bow-v1":
        assessment_map = {
            item["candidate_id"]: item for item in report["selection_gate_assessments"]
        }
        assert selected_candidate_id in assessment_map
        assert assessment_map[selected_candidate_id]["qualifies"] is True


def test_invalid_similarity_threshold_raises(tmp_path: Path) -> None:
    eval_path = tmp_path / "eval.jsonl"
    lexicon_path = tmp_path / "lexicon.json"
    _write_eval(eval_path)
    _write_lexicon(lexicon_path)

    with pytest.raises(ValueError, match="similarity_threshold"):
        run_embedding_bakeoff(
            input_path=eval_path,
            lexicon_path=lexicon_path,
            similarity_threshold=1.5,
            enable_optional_models=False,
        )
