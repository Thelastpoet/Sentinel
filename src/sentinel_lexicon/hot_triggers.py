from __future__ import annotations

import importlib
import json
import logging
import os
import re
import unicodedata
from collections.abc import Iterable
from functools import lru_cache

from sentinel_lexicon.lexicon_repository import LexiconEntry

logger = logging.getLogger(__name__)

TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']+")
DEFAULT_REDIS_SOCKET_TIMEOUT_SECONDS = 0.05
DEFAULT_REDIS_KEY_PREFIX = "sentinel:hot-triggers"
HOT_TRIGGER_MIN_SEVERITY = 3


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("’", "'")
    return normalized.lower()


def _tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(_normalize_text(value))


def _hot_trigger_key(lexicon_version: str) -> str:
    prefix = os.getenv("SENTINEL_REDIS_HOT_TRIGGER_KEY_PREFIX", DEFAULT_REDIS_KEY_PREFIX)
    return f"{prefix}:{lexicon_version}"


def _redis_socket_timeout_seconds() -> float:
    raw = os.getenv("SENTINEL_REDIS_SOCKET_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_REDIS_SOCKET_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_REDIS_SOCKET_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_REDIS_SOCKET_TIMEOUT_SECONDS
    return value


def _is_hot_trigger_candidate(entry: LexiconEntry) -> bool:
    if entry.action != "BLOCK":
        return False
    if entry.severity < HOT_TRIGGER_MIN_SEVERITY:
        return False
    return len(_tokenize(entry.term)) == 1


def _serialize_entry(entry: LexiconEntry) -> str:
    return json.dumps(
        {
            "term": entry.term,
            "action": entry.action,
            "label": entry.label,
            "reason_code": entry.reason_code,
            "severity": entry.severity,
            "lang": entry.lang,
        }
    )


def _deserialize_entry(raw: str) -> LexiconEntry | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    try:
        return LexiconEntry(
            term=str(payload["term"]),
            action=str(payload["action"]),
            label=str(payload["label"]),
            reason_code=str(payload["reason_code"]),
            severity=int(payload["severity"]),
            lang=str(payload["lang"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _build_hot_trigger_mapping(entries: Iterable[LexiconEntry]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in entries:
        if not _is_hot_trigger_candidate(entry):
            continue
        tokens = _tokenize(entry.term)
        if len(tokens) != 1:
            continue
        mapping[tokens[0]] = _serialize_entry(entry)
    return mapping


@lru_cache(maxsize=1)
def _build_redis_client():
    redis_url = os.getenv("SENTINEL_REDIS_URL")
    if not redis_url:
        return None

    try:
        redis = importlib.import_module("redis")
    except ModuleNotFoundError:
        logger.warning("redis package unavailable; hot trigger cache disabled")
        return None

    timeout = _redis_socket_timeout_seconds()
    try:
        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=timeout,
            socket_connect_timeout=timeout,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("redis unavailable; hot trigger cache disabled: %s", exc)
        return None


def _get_redis_client():
    return _build_redis_client()


def reset_hot_trigger_cache() -> None:
    _build_redis_client.cache_clear()


def _prime_hot_triggers(client, key: str, entries: Iterable[LexiconEntry]) -> None:
    mapping = _build_hot_trigger_mapping(entries)
    if not mapping:
        return

    if client.exists(key):
        return

    pipe = client.pipeline()
    pipe.hset(key, mapping=mapping)
    ttl_raw = os.getenv("SENTINEL_REDIS_HOT_TRIGGER_TTL_SECONDS")
    if ttl_raw:
        try:
            ttl_seconds = int(ttl_raw)
        except ValueError:
            ttl_seconds = 0
        if ttl_seconds > 0:
            pipe.expire(key, ttl_seconds)
    pipe.execute()


def find_hot_trigger_matches(
    text: str,
    *,
    lexicon_version: str,
    entries: Iterable[LexiconEntry],
) -> list[LexiconEntry]:
    client = _get_redis_client()
    if client is None:
        return []

    tokens = list(dict.fromkeys(_tokenize(text)))
    if not tokens:
        return []

    key = _hot_trigger_key(lexicon_version)
    try:
        _prime_hot_triggers(client, key, entries)
        values = client.hmget(key, tokens)
    except Exception as exc:
        logger.warning("redis hot trigger lookup failed; falling back: %s", exc)
        return []

    matches: list[LexiconEntry] = []
    for value in values:
        if value is None:
            continue
        entry = _deserialize_entry(value)
        if entry is not None:
            matches.append(entry)
    return matches
