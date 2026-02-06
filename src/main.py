"""FastAPI application entry point with lifespan management."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.clients import router as clients_router
from src.api.demo import router as demo_router
from src.api.health import router as health_router
from src.api.integrations import router as integrations_router
from src.api.middleware import RequestContextMiddleware
from src.api.review import router as review_router
from src.api.status import router as status_router
from src.api.tasks import router as tasks_router
from src.core.config import settings
from src.core.database import create_engine, create_session_factory
from src.core.logging import configure_logging, get_logger
from src.core.redis import create_redis_pool
from src.core.sentry import init_sentry

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle resources.

    Startup:
        - Configure structured logging
        - Initialize Sentry error tracking
        - Create database engine and session factory
        - Establish Redis connection pool

    Shutdown:
        - Close Redis connections
        - Dispose database engine
    """
    # Configure logging first
    configure_logging()
    logger.info("Starting application", environment=settings.environment)

    # Initialize error tracking
    init_sentry()

    # Create database engine and session factory
    app.state.db_engine = create_engine()
    app.state.async_session = create_session_factory(app.state.db_engine)
    logger.info("Database engine created")

    # Create Redis connection pool
    app.state.redis = await create_redis_pool()
    logger.info("Redis pool created")

    yield

    # Shutdown
    logger.info("Shutting down application")

    # Close Redis connections
    await app.state.redis.aclose()
    logger.info("Redis pool closed")

    # Dispose database engine
    await app.state.db_engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(
    title="Rookie",
    description="AI-powered CPA firm assistant for client file management",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request context middleware
app.add_middleware(RequestContextMiddleware)

# Include routers
app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(clients_router)
app.include_router(demo_router)
app.include_router(review_router)
app.include_router(status_router)
app.include_router(integrations_router)
