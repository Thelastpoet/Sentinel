from __future__ import annotations

import logging
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from sentinel_lexicon.lexicon_repository import (
    FallbackLexiconRepository,
    FileLexiconRepository,
    LexiconEntry,
    PostgresLexiconRepository,
)

logger = logging.getLogger(__name__)
TERM_TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']+")
WORD_BOUNDARY_CHARS = r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']"


class LexiconMatcher:
    def __init__(self, version: str, entries: list[LexiconEntry]) -> None:
        self.version = version
        self.entries = entries
        self._compiled_entries: list[tuple[LexiconEntry, re.Pattern[str]]] = [
            (entry, _compile_term_pattern(entry.term)) for entry in entries
        ]

    def match(self, text: str) -> list[LexiconEntry]:
        normalized = _normalize_text(text)
        matches: list[LexiconEntry] = []
        for entry, pattern in self._compiled_entries:
            if pattern.search(normalized):
                matches.append(entry)
        return matches


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("’", "'")
    return normalized.lower()


def _compile_term_pattern(term: str) -> re.Pattern[str]:
    normalized = _normalize_text(term).strip()
    if not normalized:
        return re.compile(r"(?!x)x")
    tokens = TERM_TOKEN_PATTERN.findall(normalized)

    if not tokens:
        return re.compile(re.escape(normalized))

    boundary_start = rf"(?<!{WORD_BOUNDARY_CHARS})"
    boundary_end = rf"(?!{WORD_BOUNDARY_CHARS})"
    token_pattern = r"[\W_]+".join(re.escape(token) for token in tokens)
    compiled = rf"{boundary_start}{token_pattern}{boundary_end}"
    try:
        return re.compile(compiled)
    except re.error as exc:
        logger.warning(
            "failed to compile lexicon regex for term=%r; using escaped literal: %s",
            term,
            exc,
        )
        return re.compile(re.escape(normalized))


def _default_lexicon_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "lexicon_seed.json"


def _build_repository_from_env():
    file_repo = FileLexiconRepository(
        Path(os.getenv("SENTINEL_LEXICON_PATH", str(_default_lexicon_path())))
    )
    database_url = os.getenv("SENTINEL_DATABASE_URL")
    if not database_url:
        return file_repo
    return FallbackLexiconRepository(
        primary=PostgresLexiconRepository(database_url),
        fallback=file_repo,
        logger=logger,
    )


def reset_lexicon_cache() -> None:
    get_lexicon_matcher.cache_clear()


@lru_cache(maxsize=1)
def get_lexicon_matcher() -> LexiconMatcher:
    repository = _build_repository_from_env()
    snapshot = repository.fetch_active()
    return LexiconMatcher(version=snapshot.version, entries=snapshot.entries)
