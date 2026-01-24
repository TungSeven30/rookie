"""FastAPI dependency injection for database and Redis access."""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    import redis.asyncio as redis


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session from the app's session factory.

    Args:
        request: FastAPI request containing app state.

    Yields:
        AsyncSession for database operations with automatic commit/rollback.
    """
    async with request.app.state.async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis(request: Request) -> "redis.Redis":
    """Get Redis connection pool from app state.

    Args:
        request: FastAPI request containing app state.

    Returns:
        Redis connection pool for cache/queue operations.
    """
    return request.app.state.redis
