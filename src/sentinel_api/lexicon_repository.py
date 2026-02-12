from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class LexiconEntry:
    term: str
    action: str
    label: str
    reason_code: str
    severity: int
    lang: str


@dataclass(frozen=True)
class LexiconSnapshot:
    version: str
    entries: list[LexiconEntry]


class LexiconRepository(Protocol):
    def fetch_active(self) -> LexiconSnapshot: ...


class FileLexiconRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def fetch_active(self) -> LexiconSnapshot:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        entries = [
            LexiconEntry(
                term=item["term"].lower(),
                action=item["action"],
                label=item["label"],
                reason_code=item["reason_code"],
                severity=int(item["severity"]),
                lang=item["lang"],
            )
            for item in payload["entries"]
        ]
        return LexiconSnapshot(version=str(payload["version"]), entries=entries)


class PostgresLexiconRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def fetch_active(self) -> LexiconSnapshot:
        psycopg = importlib.import_module("psycopg")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT version
                    FROM lexicon_releases
                    WHERE status = 'active'
                    ORDER BY activated_at DESC NULLS LAST, updated_at DESC, version DESC
                    LIMIT 1
                    """
                )
                active = cur.fetchone()
                if not active:
                    raise ValueError("no active lexicon release in database")
                active_version = str(active[0])

                cur.execute(
                    """
                    SELECT term, action, label, reason_code, severity, lang
                    FROM lexicon_entries
                    WHERE status = 'active'
                      AND lexicon_version = %s
                    ORDER BY id ASC
                    """,
                    (active_version,),
                )
                rows = cur.fetchall()

        if not rows:
            raise ValueError("no active lexicon entries for active release")
        entries = [
            LexiconEntry(
                term=str(row[0]).lower(),
                action=str(row[1]),
                label=str(row[2]),
                reason_code=str(row[3]),
                severity=int(row[4]),
                lang=str(row[5]),
            )
            for row in rows
        ]
        return LexiconSnapshot(version=active_version, entries=entries)


class FallbackLexiconRepository:
    def __init__(
        self, primary: LexiconRepository, fallback: LexiconRepository, logger
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.logger = logger

    def fetch_active(self) -> LexiconSnapshot:
        try:
            return self.primary.fetch_active()
        except Exception as exc:
            self.logger.warning(
                "failed to load lexicon from primary backend; using fallback: %s", exc
            )
            return self.fallback.fetch_active()
