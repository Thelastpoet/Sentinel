from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

import sentinel_core.embedding_bakeoff as bakeoff
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


def test_embedding_dim_is_384_for_e5_and_labse() -> None:
    candidates = bakeoff._build_candidates(enable_optional_models=True)
    dim_map = {candidate.candidate_id: candidate.embedding_dim for candidate in candidates}
    assert dim_map["e5-multilingual-small"] == 384
    assert dim_map["labse"] == 384


def test_e5_small_returns_384_floats(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeArray(list):
        def tolist(self):  # type: ignore[override]
            return list(self)

    class _FakeSentenceTransformer:
        def __init__(self, name: str) -> None:
            assert name == "intfloat/multilingual-e5-small"

        def encode(self, text: str, *, normalize_embeddings: bool):
            assert normalize_embeddings is True
            assert text.startswith("query: ")
            return _FakeArray([0.0] * 384)

    fake_module = types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    bakeoff._load_e5_small_model.cache_clear()

    embedding = bakeoff._embed("e5-multilingual-small", "test")
    assert len(embedding) == 384


def test_labse_returns_384_floats(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeArray(list):
        def tolist(self):  # type: ignore[override]
            return list(self)

    class _FakeSentenceTransformer:
        def __init__(self, name: str) -> None:
            assert name == "sentence-transformers/LaBSE"

        def encode(self, text: str, *, normalize_embeddings: bool):
            assert normalize_embeddings is True
            assert text == "test"
            return _FakeArray([0.0] * 384)

    fake_module = types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    bakeoff._load_labse_model.cache_clear()

    embedding = bakeoff._embed("labse", "test")
    assert len(embedding) == 384
