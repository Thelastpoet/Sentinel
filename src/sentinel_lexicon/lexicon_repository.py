from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

DEFAULT_METADATA_TIMESTAMP = "1970-01-01T00:00:00+00:00"
VALID_ENTRY_STATUSES = {"active", "deprecated"}


def _normalize_timestamp(value: object | None) -> str:
    if value is None:
        return DEFAULT_METADATA_TIMESTAMP
    normalized = str(value).strip()
    if not normalized:
        return DEFAULT_METADATA_TIMESTAMP
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return DEFAULT_METADATA_TIMESTAMP
    return normalized


def _normalize_status(value: object | None) -> str:
    if value is None:
        return "active"
    normalized = str(value).strip().lower()
    if normalized in VALID_ENTRY_STATUSES:
        return normalized
    return "active"


def _normalize_change_history(
    value: object | None,
    *,
    fallback_at: str,
) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list):
        return (
            {
                "action": "seed_import",
                "actor": "system",
                "details": "legacy-metadata-placeholder",
                "created_at": fallback_at,
            },
        )

    normalized_events: list[dict[str, str]] = []
    for event in value:
        if not isinstance(event, dict):
            continue
        action = str(event.get("action", "")).strip().lower()
        actor = str(event.get("actor", "system")).strip() or "system"
        details = str(event.get("details", "")).strip()
        created_at = _normalize_timestamp(event.get("created_at"))
        if not action:
            continue
        normalized_events.append(
            {
                "action": action,
                "actor": actor,
                "details": details,
                "created_at": created_at,
            }
        )

    if normalized_events:
        return tuple(normalized_events)
    return (
        {
            "action": "seed_import",
            "actor": "system",
            "details": "legacy-metadata-placeholder",
            "created_at": fallback_at,
        },
    )


@dataclass(frozen=True)
class LexiconEntry:
    term: str
    action: str
    label: str
    reason_code: str
    severity: int
    lang: str
    first_seen: str = DEFAULT_METADATA_TIMESTAMP
    last_seen: str = DEFAULT_METADATA_TIMESTAMP
    status: str = "active"
    change_history: tuple[dict[str, str], ...] = ()


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
                first_seen=_normalize_timestamp(item.get("first_seen")),
                last_seen=_normalize_timestamp(item.get("last_seen")),
                status=_normalize_status(item.get("status")),
                change_history=_normalize_change_history(
                    item.get("change_history"),
                    fallback_at=_normalize_timestamp(item.get("first_seen")),
                ),
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
                    SELECT
                      term,
                      action,
                      label,
                      reason_code,
                      severity,
                      lang,
                      first_seen::text,
                      last_seen::text,
                      status,
                      COALESCE(change_history, '[]'::jsonb)
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
                first_seen=_normalize_timestamp(row[6] if len(row) > 6 else None),
                last_seen=_normalize_timestamp(row[7] if len(row) > 7 else None),
                status=_normalize_status(row[8] if len(row) > 8 else None),
                change_history=_normalize_change_history(
                    row[9] if len(row) > 9 else None,
                    fallback_at=_normalize_timestamp(row[6] if len(row) > 6 else None),
                ),
            )
            for row in rows
        ]
        return LexiconSnapshot(version=active_version, entries=entries)


class FallbackLexiconRepository:
    def __init__(self, primary: LexiconRepository, fallback: LexiconRepository, logger) -> None:
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
