from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sentinel_core.models import ModerationContext, ModerationResponse

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "sentinel:result:"


def make_cache_key(
    text: str,
    *,
    policy_version: str,
    lexicon_version: str,
    model_version: str,
    pack_versions: dict[str, str],
    deployment_stage: str,
    context: ModerationContext | None,
) -> str:
    context_payload: dict[str, Any]
    if context is None:
        context_payload = {}
    else:
        context_payload = context.model_dump()
    canonical = {
        "text": text,
        "policy_version": policy_version,
        "lexicon_version": lexicon_version,
        "model_version": model_version,
        "pack_versions": dict(pack_versions),
        "deployment_stage": deployment_stage,
        "context": context_payload,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return f"{CACHE_KEY_PREFIX}{digest}"


def get_cached_result(cache_key: str, redis_url: str) -> ModerationResponse | None:
    try:
        import redis

        client = redis.Redis.from_url(redis_url, decode_responses=True)
        cached = client.get(cache_key)
        if not cached:
            return None
        return ModerationResponse.model_validate_json(cached)
    except Exception as exc:
        logger.debug("result cache read failed: %s", exc)
        return None


def set_cached_result(
    cache_key: str,
    result: ModerationResponse,
    redis_url: str,
    *,
    ttl: int,
) -> None:
    normalized_ttl = max(1, int(ttl))
    try:
        import redis

        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.set(cache_key, result.model_dump_json(), ex=normalized_ttl)
    except Exception as exc:
        logger.debug("result cache write failed: %s", exc)
