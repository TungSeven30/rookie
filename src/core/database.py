"""Async database engine factory and session management."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import settings

# Import all models to register them with Base.metadata
from src.models import (  # noqa: F401
    AgentLog,
    AgentMetric,
    Base,
    Client,
    ClientProfileEntry,
    DocumentEmbedding,
    Escalation,
    FeedbackEntry,
    SkillEmbedding,
    SkillFile,
    Task,
    TaskArtifact,
)


def create_engine(
    database_url: str | None = None,
    **engine_options: Any,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    Args:
        database_url: PostgreSQL connection URL. Defaults to settings.database_url.
        **engine_options: Additional options passed to create_async_engine.

    Returns:
        Configured AsyncEngine instance.
    """
    url = database_url or settings.database_url

    default_options = {
        "pool_size": 20,
        "max_overflow": 0,
        "pool_pre_ping": True,
        "echo": settings.debug,
    }
    default_options.update(engine_options)

    return create_async_engine(url, **default_options)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Args:
        engine: AsyncEngine instance to bind sessions to.

    Returns:
        Configured async_sessionmaker instance.
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# Default engine and session factory (lazily initialized)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the default async engine.

    Returns:
        The default AsyncEngine instance.
    """
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the default session factory.

    Returns:
        The default async_sessionmaker instance.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory(get_engine())
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    Yields:
        AsyncSession instance for database operations.

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
