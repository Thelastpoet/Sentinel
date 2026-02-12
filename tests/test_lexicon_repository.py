from __future__ import annotations

import json

from sentinel_api.lexicon_repository import (
    FallbackLexiconRepository,
    FileLexiconRepository,
    LexiconEntry,
    LexiconSnapshot,
)


class _FailingRepo:
    def fetch_active(self) -> LexiconSnapshot:
        raise RuntimeError("primary unavailable")


class _StaticRepo:
    def __init__(self, snapshot: LexiconSnapshot) -> None:
        self.snapshot = snapshot

    def fetch_active(self) -> LexiconSnapshot:
        return self.snapshot


def test_file_repository_reads_json(tmp_path) -> None:
    seed = {
        "version": "hatelex-v1.0",
        "entries": [
            {
                "term": "alpha",
                "action": "REVIEW",
                "label": "DOGWHISTLE_WATCH",
                "reason_code": "R_DOGWHISTLE_CONTEXT_REQUIRED",
                "severity": 2,
                "lang": "en",
            }
        ],
    }
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(seed), encoding="utf-8")

    repo = FileLexiconRepository(path)
    snapshot = repo.fetch_active()

    assert snapshot.version == "hatelex-v1.0"
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].term == "alpha"


def test_fallback_repository_uses_primary_when_healthy() -> None:
    primary_snapshot = LexiconSnapshot(
        version="hatelex-v2.0",
        entries=[
            LexiconEntry(
                term="x",
                action="BLOCK",
                label="INCITEMENT_VIOLENCE",
                reason_code="R_INCITE_CALL_TO_HARM",
                severity=3,
                lang="en",
            )
        ],
    )
    primary = _StaticRepo(primary_snapshot)
    fallback = _StaticRepo(LexiconSnapshot(version="hatelex-v1.0", entries=[]))

    class _NoOpLogger:
        def warning(self, *_args, **_kwargs) -> None:
            return None

    repo = FallbackLexiconRepository(primary=primary, fallback=fallback, logger=_NoOpLogger())
    snapshot = repo.fetch_active()
    assert snapshot.version == "hatelex-v2.0"


def test_fallback_repository_uses_fallback_on_primary_failure() -> None:
    fallback_snapshot = LexiconSnapshot(
        version="hatelex-v1.0",
        entries=[
            LexiconEntry(
                term="y",
                action="REVIEW",
                label="DOGWHISTLE_WATCH",
                reason_code="R_DOGWHISTLE_CONTEXT_REQUIRED",
                severity=2,
                lang="en",
            )
        ],
    )
    primary = _FailingRepo()
    fallback = _StaticRepo(fallback_snapshot)

    class _NoOpLogger:
        def warning(self, *_args, **_kwargs) -> None:
            return None

    repo = FallbackLexiconRepository(primary=primary, fallback=fallback, logger=_NoOpLogger())
    snapshot = repo.fetch_active()
    assert snapshot.version == "hatelex-v1.0"
    assert snapshot.entries[0].term == "y"
