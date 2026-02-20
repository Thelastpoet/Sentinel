from __future__ import annotations

import hashlib
import importlib
import logging
import math
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from sentinel_lexicon.lexicon_repository import LexiconEntry

logger = logging.getLogger(__name__)

VECTOR_DIMENSION = 64
VECTOR_MODEL = "hash-bow-v1"
E5_SMALL_MODEL = "e5-multilingual-small-v1"
E5_SMALL_DIMENSION = 384
DEFAULT_VECTOR_MATCH_THRESHOLD = 0.82
DEFAULT_STATEMENT_TIMEOUT_MS = 60
TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']+")


@dataclass(frozen=True)
class VectorMatch:
    entry: LexiconEntry
    similarity: float
    match_id: str


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("’", "'")
    return normalized.lower().strip()


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(_normalize_text(text))


def _feature_stream(text: str) -> list[tuple[str, float]]:
    tokens = _tokenize(text)
    if not tokens:
        return []

    features: list[tuple[str, float]] = []
    for token in tokens:
        features.append((f"tok:{token}", 1.0))

    for idx in range(len(tokens) - 1):
        features.append((f"bigram:{tokens[idx]}_{tokens[idx + 1]}", 1.2))

    for token in tokens:
        compact = token.replace("'", "")
        if len(compact) < 3:
            continue
        for start in range(0, len(compact) - 2):
            gram = compact[start : start + 3]
            features.append((f"tri:{gram}", 0.5))

    return features


def embed_text(text: str) -> list[float]:
    features = _feature_stream(text)
    if not features:
        return [0.0] * VECTOR_DIMENSION

    vector = [0.0] * VECTOR_DIMENSION
    for feature, weight in features:
        # Signed feature hashing keeps memory/latency bounded at fixed dimension.
        # Collisions are expected with this projection and are tolerated here because
        # the vector path is REVIEW-only and threshold-gated before policy impact.
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=16).digest()
        index = int.from_bytes(digest[0:2], byteorder="big") % VECTOR_DIMENSION
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return [0.0] * VECTOR_DIMENSION
    return [value / norm for value in vector]


@lru_cache(maxsize=1)
def _load_e5_small_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("intfloat/multilingual-e5-small")


def _embed_passage(text: str, *, embedding_model: str) -> tuple[int, list[float]] | None:
    if embedding_model == VECTOR_MODEL:
        return VECTOR_DIMENSION, embed_text(text)
    if embedding_model == E5_SMALL_MODEL:
        model = _load_e5_small_model()
        embedding = model.encode(f"passage: {text}", normalize_embeddings=True)
        values = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
        return E5_SMALL_DIMENSION, values
    logger.warning("unsupported embedding_model for lexicon embeddings: %s", embedding_model)
    return None


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _vector_match_threshold() -> float:
    raw = os.getenv("SENTINEL_VECTOR_MATCH_THRESHOLD")
    if raw is None:
        return DEFAULT_VECTOR_MATCH_THRESHOLD
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_VECTOR_MATCH_THRESHOLD
    if value < 0 or value > 1:
        return DEFAULT_VECTOR_MATCH_THRESHOLD
    return value


def _vector_statement_timeout_ms() -> int:
    raw = os.getenv("SENTINEL_VECTOR_STATEMENT_TIMEOUT_MS")
    if raw is None:
        return DEFAULT_STATEMENT_TIMEOUT_MS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_STATEMENT_TIMEOUT_MS
    if value <= 0:
        return DEFAULT_STATEMENT_TIMEOUT_MS
    return value


def _vector_matching_enabled() -> bool:
    raw = os.getenv("SENTINEL_VECTOR_MATCH_ENABLED")
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _database_url() -> str | None:
    value = os.getenv("SENTINEL_DATABASE_URL")
    if not value:
        return None
    return value


def _get_psycopg_module():
    return importlib.import_module("psycopg")


def _maybe_get_pool(database_url: str):
    try:
        from sentinel_db.pool import peek_pool  # type: ignore[import-not-found]
    except Exception:
        return None
    del database_url
    return peek_pool()


def _apply_statement_timeout(cur) -> None:
    timeout_ms = _vector_statement_timeout_ms()
    cur.execute(f"SET LOCAL statement_timeout = '{timeout_ms}ms'")


@lru_cache(maxsize=64)
def _ensure_embeddings_for_version(
    database_url: str,
    lexicon_version: str,
    embedding_model: str,
) -> None:
    psycopg = _get_psycopg_module()
    pool = _maybe_get_pool(database_url)
    conn_ctx = pool.connection() if pool is not None else psycopg.connect(database_url)
    with conn_ctx as conn:
        with conn.cursor() as cur:
            _apply_statement_timeout(cur)
            cur.execute(
                """
                SELECT le.id, le.term
                FROM lexicon_entries AS le
                LEFT JOIN lexicon_entry_embeddings_v2 AS emb
                  ON emb.lexicon_entry_id = le.id
                 AND emb.embedding_model = %s
                WHERE le.status = 'active'
                  AND le.lexicon_version = %s
                  AND emb.lexicon_entry_id IS NULL
                ORDER BY le.id ASC
                """,
                (embedding_model, lexicon_version),
            )
            rows = cur.fetchall()

            for row in rows:
                lexicon_entry_id = int(row[0])
                term = str(row[1])
                embedded = _embed_passage(term, embedding_model=embedding_model)
                if embedded is None:
                    continue
                embedding_dim, embedding_values = embedded
                embedding_literal = _vector_literal(embedding_values)
                cur.execute(
                    """
                    INSERT INTO lexicon_entry_embeddings_v2
                      (lexicon_entry_id, embedding, embedding_model, embedding_dim, updated_at)
                    VALUES
                      (%s, %s::vector, %s, %s, NOW())
                    ON CONFLICT (lexicon_entry_id, embedding_model)
                    DO UPDATE SET
                      embedding = EXCLUDED.embedding,
                      embedding_dim = EXCLUDED.embedding_dim,
                      updated_at = NOW()
                    """,
                    (lexicon_entry_id, embedding_literal, embedding_model, embedding_dim),
                )
        conn.commit()


def reset_vector_match_cache() -> None:
    _ensure_embeddings_for_version.cache_clear()


def find_vector_match(
    text: str,
    *,
    lexicon_version: str,
    query_embedding: list[float],
    embedding_model: str,
    min_similarity: float | None = None,
) -> VectorMatch | None:
    if not _vector_matching_enabled():
        return None

    database_url = _database_url()
    if database_url is None:
        return None

    try:
        _ensure_embeddings_for_version(database_url, lexicon_version, embedding_model)
    except Exception as exc:
        logger.warning("vector embedding sync failed; falling back: %s", exc)
        return None

    del text
    if not any(query_embedding):
        return None
    query_vector_literal = _vector_literal(query_embedding)

    threshold = _vector_match_threshold()
    if min_similarity is not None:
        if 0 <= min_similarity <= 1:
            threshold = min_similarity
        else:
            logger.warning(
                "invalid phase vector threshold override; using default: %s",
                min_similarity,
            )
    psycopg = _get_psycopg_module()

    try:
        pool = _maybe_get_pool(database_url)
        conn_ctx = pool.connection() if pool is not None else psycopg.connect(database_url)
        with conn_ctx as conn:
            with conn.cursor() as cur:
                _apply_statement_timeout(cur)
                cur.execute(
                    """
                    SELECT
                      le.id,
                      le.term,
                      le.action,
                      le.label,
                      le.reason_code,
                      le.severity,
                      le.lang,
                      (1 - (emb.embedding <=> %s::vector))::float8 AS similarity
                    FROM lexicon_entries AS le
                    JOIN lexicon_entry_embeddings_v2 AS emb
                      ON emb.lexicon_entry_id = le.id
                    WHERE le.status = 'active'
                      AND le.lexicon_version = %s
                      AND le.action = 'REVIEW'
                      AND emb.embedding_model = %s
                    ORDER BY emb.embedding <=> %s::vector ASC, le.id ASC
                    LIMIT 1
                    """,
                    (
                        query_vector_literal,
                        lexicon_version,
                        embedding_model,
                        query_vector_literal,
                    ),
                )
                row = cur.fetchone()
    except Exception as exc:
        logger.warning("vector similarity lookup failed; falling back: %s", exc)
        return None

    if row is None:
        return None

    similarity = float(row[7])
    if not math.isfinite(similarity):
        logger.warning(
            "vector similarity was non-finite; discarding candidate "
            "(lexicon_version=%s, match_id=%s, raw_similarity=%s)",
            lexicon_version,
            row[0],
            row[7],
        )
        return None
    similarity = max(0.0, min(1.0, similarity))
    if similarity < threshold:
        return None

    entry = LexiconEntry(
        term=str(row[1]),
        action=str(row[2]),
        label=str(row[3]),
        reason_code=str(row[4]),
        severity=int(row[5]),
        lang=str(row[6]),
    )
    return VectorMatch(
        entry=entry,
        similarity=similarity,
        match_id=str(row[0]),
    )
