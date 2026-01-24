"""Redis connection pool for job queue, caching, and circuit breaker state."""

import redis.asyncio as redis

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


async def create_redis_pool() -> redis.Redis:
    """Create Redis connection pool.

    Usage in lifespan:
        app.state.redis = await create_redis_pool()
        yield
        await app.state.redis.aclose()

    Returns:
        Redis connection pool configured with settings.
    """
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )


async def check_redis_health(pool: redis.Redis) -> bool:
    """Check if Redis is responding.

    Args:
        pool: Redis connection pool to check.

    Returns:
        True if Redis responds to ping, False otherwise.
    """
    try:
        await pool.ping()
        return True
    except Exception as e:
        logger.exception("redis_health_check_failed", error=str(e))
        return False
