from __future__ import annotations

import pytest

from sentinel_api.lexicon_repository import PostgresLexiconRepository


class _FakeCursor:
    def __init__(self, active_row, entries_rows) -> None:
        self.active_row = active_row
        self.entries_rows = entries_rows
        self.last_query = ""

    def execute(self, query: str, params=None) -> None:
        self.last_query = query
        if "FROM lexicon_entries" in query:
            assert params is not None

    def fetchone(self):
        if "FROM lexicon_releases" in self.last_query:
            return self.active_row
        return None

    def fetchall(self):
        if "FROM lexicon_entries" in self.last_query:
            return self.entries_rows
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakePsycopg:
    def __init__(self, cursor: _FakeCursor) -> None:
        self.cursor = cursor

    def connect(self, _database_url: str) -> _FakeConnection:
        return _FakeConnection(self.cursor)


def test_postgres_repository_returns_active_release_entries(monkeypatch) -> None:
    fake_cursor = _FakeCursor(
        active_row=("hatelex-v3.0",),
        entries_rows=[
            (
                "kill",
                "BLOCK",
                "INCITEMENT_VIOLENCE",
                "R_INCITE_CALL_TO_HARM",
                3,
                "en",
            )
        ],
    )
    monkeypatch.setattr(
        "sentinel_api.lexicon_repository.importlib.import_module",
        lambda _: _FakePsycopg(fake_cursor),
    )
    repo = PostgresLexiconRepository("postgresql://example")
    snapshot = repo.fetch_active()
    assert snapshot.version == "hatelex-v3.0"
    assert snapshot.entries[0].term == "kill"


def test_postgres_repository_raises_when_no_active_release(monkeypatch) -> None:
    fake_cursor = _FakeCursor(active_row=None, entries_rows=[])
    monkeypatch.setattr(
        "sentinel_api.lexicon_repository.importlib.import_module",
        lambda _: _FakePsycopg(fake_cursor),
    )
    repo = PostgresLexiconRepository("postgresql://example")
    with pytest.raises(ValueError, match="no active lexicon release"):
        repo.fetch_active()


def test_postgres_repository_raises_when_active_release_has_no_entries(monkeypatch) -> None:
    fake_cursor = _FakeCursor(active_row=("hatelex-v3.0",), entries_rows=[])
    monkeypatch.setattr(
        "sentinel_api.lexicon_repository.importlib.import_module",
        lambda _: _FakePsycopg(fake_cursor),
    )
    repo = PostgresLexiconRepository("postgresql://example")
    with pytest.raises(ValueError, match="no active lexicon entries for active release"):
        repo.fetch_active()

