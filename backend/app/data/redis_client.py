"""Async Redis client for real-time price cache and state."""

import redis.asyncio as redis
import structlog

from app.config.settings import settings

logger = structlog.get_logger()

redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get the Redis client instance, creating it if needed."""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
