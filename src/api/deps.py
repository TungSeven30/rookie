"""FastAPI dependency injection for database and Redis access."""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from fastapi import Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
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


async def verify_demo_api_key(
    x_demo_api_key: str | None = Header(default=None, alias="X-Demo-Api-Key"),
    demo_api_key: str | None = Query(default=None, alias="demo_api_key"),
) -> None:
    """Verify API key for demo endpoints.

    Args:
        x_demo_api_key: API key from X-Demo-Api-Key header.

    Raises:
        HTTPException: If API key is missing or invalid.
    """
    if not settings.demo_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo API key is not configured",
        )
    api_key = x_demo_api_key or demo_api_key
    if api_key != settings.demo_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid demo API key",
        )
