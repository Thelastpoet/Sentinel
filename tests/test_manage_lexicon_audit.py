from __future__ import annotations

from scripts import manage_lexicon_release as mlr


class _CursorWithRows:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))

    def fetchall(self):
        return self.rows


def test_write_audit_event_inserts_expected_values() -> None:
    cursor = _CursorWithRows(rows=[])
    mlr.write_audit_event(
        cursor,
        release_version="hatelex-v2.1",
        action="activate",
        actor="tester",
        details="status=active",
    )
    assert len(cursor.executed) == 1
    _, params = cursor.executed[0]
    assert params == (
        "hatelex-v2.1",
        "activate",
        "tester",
        "status=active",
        "governance_audit",
    )


def test_list_audit_events_by_version_uses_filter() -> None:
    rows = [(1, "hatelex-v2.1", "activate", "tester", "status=active", "2026-01-01")]
    cursor = _CursorWithRows(rows=rows)
    result = mlr.list_audit_events(cursor, version="hatelex-v2.1", limit=5)
    assert result == rows
    _, params = cursor.executed[0]
    assert params == ("hatelex-v2.1", 5)


def test_list_audit_events_without_version_caps_limit() -> None:
    cursor = _CursorWithRows(rows=[])
    mlr.list_audit_events(cursor, version=None, limit=9999)
    _, params = cursor.executed[0]
    assert params == (500,)
