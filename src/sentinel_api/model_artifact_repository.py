from __future__ import annotations

import importlib
import os
import time
from dataclasses import dataclass

from sentinel_api.logging import get_logger

logger = get_logger("sentinel.model_artifact_repository")

MODEL_ARTIFACT_CACHE_TTL_SECONDS = 5.0


@dataclass
class _ModelArtifactCache:
    database_url: str | None = None
    model_id: str | None = None
    expires_at: float = 0.0


_CACHE = _ModelArtifactCache()


def reset_model_artifact_cache() -> None:
    _CACHE.database_url = None
    _CACHE.model_id = None
    _CACHE.expires_at = 0.0


def _fetch_active_model_id(database_url: str) -> str | None:
    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT model_id
                FROM model_artifacts
                WHERE status = 'active'
                ORDER BY activated_at DESC NULLS LAST, updated_at DESC, model_id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
    if row is None:
        return None
    return str(row[0])


def resolve_runtime_model_version(default_model_version: str) -> str:
    database_url = os.getenv("SENTINEL_DATABASE_URL")
    if database_url is None or not database_url.strip():
        return default_model_version
    normalized_database_url = database_url.strip()
    now = time.monotonic()
    if _CACHE.database_url == normalized_database_url and now < _CACHE.expires_at:
        return _CACHE.model_id or default_model_version

    try:
        active_model_id = _fetch_active_model_id(normalized_database_url)
    except Exception as exc:
        logger.warning(
            "failed to resolve active model artifact; using policy config model_version: %s",
            exc,
        )
        _CACHE.database_url = normalized_database_url
        _CACHE.model_id = None
        _CACHE.expires_at = now + MODEL_ARTIFACT_CACHE_TTL_SECONDS
        return default_model_version

    _CACHE.database_url = normalized_database_url
    _CACHE.model_id = active_model_id
    _CACHE.expires_at = now + MODEL_ARTIFACT_CACHE_TTL_SECONDS
    if active_model_id is None:
        return default_model_version
    return active_model_id
