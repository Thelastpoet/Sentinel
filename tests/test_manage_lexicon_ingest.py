from __future__ import annotations

import json

import pytest
from scripts import manage_lexicon_release as mlr


class _RecordingCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))


def _valid_entries() -> list[dict[str, object]]:
    return [
        {
            "term": "Kill",
            "action": "block",
            "label": "incitement_violence",
            "reason_code": "r_incite_call_to_harm",
            "severity": 3,
            "lang": "EN",
        }
    ]


def test_load_ingest_entries_accepts_list(tmp_path) -> None:
    path = tmp_path / "entries.json"
    path.write_text(json.dumps(_valid_entries()), encoding="utf-8")
    entries = mlr.load_ingest_entries(str(path))
    assert len(entries) == 1


def test_load_ingest_entries_accepts_object_with_entries(tmp_path) -> None:
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({"entries": _valid_entries()}), encoding="utf-8")
    entries = mlr.load_ingest_entries(str(path))
    assert len(entries) == 1


def test_normalize_ingest_entries_rejects_bad_reason_code() -> None:
    entries = _valid_entries()
    entries[0]["reason_code"] = "invalid"
    with pytest.raises(ValueError, match="invalid reason_code"):
        mlr.normalize_ingest_entries(entries)


def test_normalize_ingest_entries_rejects_duplicate_entries() -> None:
    entries = _valid_entries() + _valid_entries()
    with pytest.raises(ValueError, match="duplicates an earlier entry"):
        mlr.normalize_ingest_entries(entries)


def test_ingest_entries_rejects_non_draft_release(monkeypatch) -> None:
    cursor = _RecordingCursor()
    monkeypatch.setattr(mlr, "get_release_status", lambda _cur, _version: "active")
    with pytest.raises(ValueError, match="ingest allowed only for draft releases"):
        mlr.ingest_entries(cursor, "hatelex-v2.2", _valid_entries())


def test_ingest_entries_inserts_normalized_entries(monkeypatch) -> None:
    cursor = _RecordingCursor()
    monkeypatch.setattr(mlr, "get_release_status", lambda _cur, _version: "draft")
    count = mlr.ingest_entries(cursor, "hatelex-v2.2", _valid_entries())
    assert count == 1
    assert len(cursor.executed) == 1
    _, params = cursor.executed[0]
    assert params is not None
    assert params[0] == "kill"
    assert params[1] == "BLOCK"
    assert params[2] == "INCITEMENT_VIOLENCE"
    assert params[3] == "R_INCITE_CALL_TO_HARM"
    assert params[6] == "hatelex-v2.2"


def test_ingest_entries_replace_existing_runs_deprecation_step(monkeypatch) -> None:
    cursor = _RecordingCursor()
    monkeypatch.setattr(mlr, "get_release_status", lambda _cur, _version: "draft")
    monkeypatch.setattr(mlr, "count_held_active_entries_for_version", lambda _cur, _version: 0)
    count = mlr.ingest_entries(
        cursor,
        "hatelex-v2.2",
        _valid_entries(),
        replace_existing=True,
    )
    assert count == 1
    assert len(cursor.executed) == 2
    assert cursor.executed[0][1] == ("hatelex-v2.2",)


def test_ingest_entries_replace_existing_rejects_held_entries(monkeypatch) -> None:
    cursor = _RecordingCursor()
    monkeypatch.setattr(mlr, "get_release_status", lambda _cur, _version: "draft")
    monkeypatch.setattr(mlr, "count_held_active_entries_for_version", lambda _cur, _version: 2)
    with pytest.raises(ValueError, match="legal-hold active entries"):
        mlr.ingest_entries(
            cursor,
            "hatelex-v2.2",
            _valid_entries(),
            replace_existing=True,
        )
