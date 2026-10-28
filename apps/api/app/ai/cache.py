"""
AI response cache — avoids re-calling the LLM for a request whose inputs
haven't changed since the last call. Backed by Redis (the same instance
already used as the Celery broker/result backend, via `settings.redis_url`).

Cache key convention (per Sprint 7 spec): task + claim ID + prompt version
+ model + the claim's last-updated timestamp. Including the claim's
`updated_at` means any edit to the claim naturally invalidates its cached
analysis — no explicit cache-invalidation step needed. Bumping a task's
entry in `_PROMPT_VERSIONS` (app/ai/gateway.py) or switching models also
naturally invalidates, for the same reason.

Never fatal: any Redis connectivity problem is treated as a cache miss
(logged, not raised) so AI features keep working even if Redis is down.
"""

import json
import logging
from datetime import datetime

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 3600

_client: redis.Redis | None = None


def _get_client() -> redis.Redis | None:
    global _client
    if _client is None:
        try:
            _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            logger.exception("Failed to create Redis client for AI response cache")
            return None
    return _client


def build_cache_key(
    *,
    task: str,
    claim_id: int,
    prompt_version: str,
    model: str,
    claim_updated_at: datetime | None,
) -> str:
    updated_marker = claim_updated_at.isoformat() if claim_updated_at else "unknown"
    return f"ai:cache:{task}:{claim_id}:{prompt_version}:{model}:{updated_marker}"


def get_cached_json(cache_key: str) -> dict | None:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(cache_key)
    except Exception:
        logger.exception("Redis GET failed for AI cache key %s (treating as miss)", cache_key)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        logger.warning("Corrupt AI cache entry for key %s — ignoring", cache_key)
        return None


def set_cached_json(cache_key: str, value: dict, *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.set(cache_key, json.dumps(value), ex=ttl_seconds)
    except Exception:
        logger.exception("Redis SET failed for AI cache key %s (non-fatal)", cache_key)
