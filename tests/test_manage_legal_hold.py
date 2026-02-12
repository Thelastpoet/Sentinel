from __future__ import annotations

import pytest
from scripts import manage_lexicon_release as mlr


class _RecordingCursor:
    def __init__(self, *, initial_rowcount: int = 1) -> None:
        self.executed: list[tuple[str, tuple | None]] = []
        self.rowcount = initial_rowcount

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))


def test_apply_release_legal_hold_writes_hold_and_audit_records() -> None:
    cursor = _RecordingCursor(initial_rowcount=1)
    mlr.apply_release_legal_hold(
        cursor,
        version="hatelex-v2.4",
        actor="ops-a",
        reason="regulatory freeze",
    )
    assert len(cursor.executed) == 3
    assert cursor.executed[0][1] == ("hatelex-v2.4",)
    assert cursor.executed[1][1] == (
        "decision_record",
        "hatelex-v2.4",
        "regulatory freeze",
        "ops-a",
    )
    assert cursor.executed[2][1] == (
        "apply_legal_hold",
        "decision_record",
        "lexicon_releases",
        "ops-a",
        1,
        "version=hatelex-v2.4 reason=regulatory freeze",
    )


def test_release_release_legal_hold_writes_release_and_audit_records() -> None:
    cursor = _RecordingCursor(initial_rowcount=1)
    mlr.release_release_legal_hold(
        cursor,
        version="hatelex-v2.4",
        actor="ops-a",
        reason="case closed",
    )
    assert len(cursor.executed) == 3
    assert cursor.executed[0][1] == ("hatelex-v2.4",)
    assert cursor.executed[1][1] == (
        "ops-a",
        "case closed",
        "decision_record",
        "hatelex-v2.4",
    )
    assert cursor.executed[2][1] == (
        "release_legal_hold",
        "decision_record",
        "lexicon_releases",
        "ops-a",
        1,
        "version=hatelex-v2.4 reason=case closed",
    )


def test_apply_release_legal_hold_rejects_missing_release() -> None:
    cursor = _RecordingCursor(initial_rowcount=0)
    with pytest.raises(ValueError, match="does not exist"):
        mlr.apply_release_legal_hold(
            cursor,
            version="hatelex-v2.9",
            actor="ops-a",
            reason="regulatory freeze",
        )
