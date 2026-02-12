from __future__ import annotations

import pytest

from scripts import manage_lexicon_release as mlr


class _RecordingCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))


def test_activate_release_rejects_release_without_entries(monkeypatch) -> None:
    cursor = _RecordingCursor()
    monkeypatch.setattr(mlr, "get_release_status", lambda _cur, _version: "draft")
    monkeypatch.setattr(mlr, "get_release_legal_hold", lambda _cur, _version: False)
    monkeypatch.setattr(mlr, "count_active_entries_for_version", lambda _cur, _version: 0)

    with pytest.raises(ValueError, match="has no active lexicon entries"):
        mlr.activate_release(cursor, "hatelex-v2.2")


def test_activate_release_updates_statuses_when_valid(monkeypatch) -> None:
    cursor = _RecordingCursor()
    monkeypatch.setattr(mlr, "get_release_status", lambda _cur, _version: "draft")
    monkeypatch.setattr(mlr, "get_release_legal_hold", lambda _cur, _version: False)
    monkeypatch.setattr(mlr, "count_active_entries_for_version", lambda _cur, _version: 5)
    monkeypatch.setattr(
        mlr, "find_active_held_release_to_deprecate", lambda _cur, _version: None
    )

    mlr.activate_release(cursor, "hatelex-v2.2")

    assert len(cursor.executed) == 2
    assert cursor.executed[0][1] == ("hatelex-v2.2",)
    assert cursor.executed[1][1] == ("hatelex-v2.2",)


def test_validate_release_fails_when_no_active_and_no_version(monkeypatch) -> None:
    monkeypatch.setattr(mlr, "get_active_release_version", lambda _cur: None)
    report = mlr.validate_release(object(), None)
    assert report["ok"] is False
    assert report["message"] == "no active release found and no version provided"


def test_validate_release_passes_for_release_with_entries(monkeypatch) -> None:
    monkeypatch.setattr(mlr, "get_release_status", lambda _cur, _version: "draft")
    monkeypatch.setattr(mlr, "count_active_entries_for_version", lambda _cur, _version: 3)
    report = mlr.validate_release(object(), "hatelex-v2.3")
    assert report["ok"] is True
    assert report["version"] == "hatelex-v2.3"
    assert report["active_entry_count"] == 3


def test_activate_release_rejects_when_release_on_legal_hold(monkeypatch) -> None:
    cursor = _RecordingCursor()
    monkeypatch.setattr(mlr, "get_release_status", lambda _cur, _version: "draft")
    monkeypatch.setattr(mlr, "get_release_legal_hold", lambda _cur, _version: True)
    monkeypatch.setattr(mlr, "count_active_entries_for_version", lambda _cur, _version: 5)

    with pytest.raises(ValueError, match="is on legal hold"):
        mlr.activate_release(cursor, "hatelex-v2.2")


def test_deprecate_release_rejects_when_release_on_legal_hold(monkeypatch) -> None:
    cursor = _RecordingCursor()
    monkeypatch.setattr(mlr, "get_release_legal_hold", lambda _cur, _version: True)
    with pytest.raises(ValueError, match="is on legal hold"):
        mlr.deprecate_release(cursor, "hatelex-v2.2")
