"""Health check endpoint for infrastructure verification."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_redis
from src.core.logging import get_logger
from src.core.redis import check_redis_health

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    db: str
    redis: str


@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HealthResponse:
    """Check application health including database and Redis connectivity.

    Returns:
        HealthResponse with status of each component.
    """
    # Check database connection
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.exception("database_health_check_failed", error=str(e))
        db_status = "disconnected"

    # Check Redis connection
    redis_pool = await get_redis(request)
    redis_healthy = await check_redis_health(redis_pool)
    redis_status = "connected" if redis_healthy else "disconnected"

    return HealthResponse(
        status="ok"
        if db_status == "connected" and redis_status == "connected"
        else "degraded",
        db=db_status,
        redis=redis_status,
    )
