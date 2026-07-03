"""Async Redis client (lazy singleton) — cache, queues, rate limits later.

Same philosophy as the DB engine: created on first use, optional in
development, disposed by the lifespan shutdown hook.
"""

import logging

from redis.asyncio import Redis, from_url

from config import Settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None


def get_redis(settings: Settings) -> Redis:
    """Return the process-wide Redis client, creating it on first use."""
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
        logger.info("Redis client created (%s)", settings.redis_url)
    return _redis


async def close_redis() -> None:
    """Close the Redis connection pool. Called on application shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("Redis client closed")
