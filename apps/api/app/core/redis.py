"""
Redis configuration and client management.
"""
from typing import AsyncGenerator, Optional

import redis.asyncio as redis
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """
    Get or create the global Redis client.
    This is used internally to maintain a single connection pool.
    """
    global _redis_client

    if _redis_client is None:
        logger.info("creating_redis_client", url=settings.REDIS_URL)
        _redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )

    return _redis_client


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """
    Dependency for getting Redis client.
    Yields the Redis client for use in route handlers.
    """
    client = await get_redis_client()
    try:
        yield client
    except Exception as e:
        logger.error("redis_operation_failed", error=str(e))
        raise


async def close_redis():
    """
    Close the Redis connection.
    Should be called during application shutdown.
    """
    global _redis_client

    if _redis_client is not None:
        logger.info("closing_redis_connection")
        await _redis_client.close()
        _redis_client = None
