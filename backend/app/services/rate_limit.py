"""Redis-backed token-bucket rate limiter with in-process fail-open fallback.

ADR 0003 D6: when multiple uvicorn workers run, the in-process `_LOCAL_BUCKETS`
dict in mcp_core is per-worker and can be bypassed by spreading requests. This
module provides a Redis-backed limiter that shares state across workers.

Fail-open policy:
- No REDIS_URL configured → use in-process fallback (single-worker dev mode).
- Redis unreachable (connection refused, timeout) → use in-process fallback
  and mark event.status="rate_limit_fallback" for visibility.

Algorithm: fixed-window counter per (hotel_id, tool_name, minute_bucket).
Simpler than sliding window and sufficient for 20-60 req/min limits.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from app.mcp_core import (
    MCPAuthError,
    _TOOL_RATE_LIMITS,
    check_rate_limit as _local_check_rate_limit,
)

logger = logging.getLogger(__name__)

_KEY_PREFIX = "ratelimit"
_DEFAULT_LIMIT = 60

_redis_client = None           # lazy-init singleton
_redis_available: Optional[bool] = None  # None = unknown, True/False = confirmed


def _get_redis_url() -> str | None:
    url = os.getenv("REDIS_URL")
    return url if url else None


def _make_client():
    """Lazy-import redis.asyncio and build a client. Returns None on failure."""
    global _redis_client, _redis_available
    if _redis_client is not None:
        return _redis_client
    url = _get_redis_url()
    if not url:
        _redis_available = False
        return None
    try:
        import redis.asyncio as aioredis  # lazy import — redis is optional in dev
        _redis_client = aioredis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        return _redis_client
    except Exception as exc:
        logger.warning("Redis client init failed, using in-process fallback: %s", exc)
        _redis_available = False
        return None


async def check_rate_limit_async(hotel_id: str, tool_name: str) -> bool:
    """Token-bucket check. Raises MCPAuthError(429) on breach.

    Returns True when Redis was used, False when the in-process fallback was
    used (caller can mark the event for observability).
    """
    limit = _TOOL_RATE_LIMITS.get(tool_name, _DEFAULT_LIMIT)
    minute_bucket = int(time.time() // 60)
    key = f"{_KEY_PREFIX}:{hotel_id}:{tool_name}:{minute_bucket}"

    client = _make_client()
    if client is None:
        _local_check_rate_limit(hotel_id, tool_name)
        return False

    try:
        # Atomic INCR + EXPIRE via pipeline — prevents key leak if expire fails
        # after a successful incr (partial Redis failure leaves a keyless counter
        # permanently blocking the hotel). Pipeline executes both or neither.
        async with client.pipeline(transaction=False) as pipe:
            pipe.incr(key)
            pipe.expire(key, 65)
            results = await pipe.execute()
        count = results[0]
    except Exception as exc:
        # Redis transient failure — fail open (ADR 0003 D6) + log for monitoring.
        global _redis_available
        _redis_available = False
        logger.warning(
            "Redis rate-limit check failed, fail-open fallback: %s", exc
        )
        _local_check_rate_limit(hotel_id, tool_name)
        return False

    if count > limit:
        raise MCPAuthError(
            429,
            "rate_limited",
            f"{limit} req/min exceeded for tool={tool_name}",
        )
    return True


async def close() -> None:
    """Close the Redis connection (lifespan shutdown)."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:  # pragma: no cover
            pass
        _redis_client = None
