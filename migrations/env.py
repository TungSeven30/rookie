"""Alembic migration environment with async PostgreSQL and pgvector support."""

import asyncio
from logging.config import fileConfig

from alembic import context
from pgvector.sqlalchemy import Vector
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.core.config import settings
from src.models import Base

# Import all models to register them with Base.metadata
from src.models import (  # noqa: F401
    AgentLog,
    AgentMetric,
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

# Alembic Config object
config = context.config

# Configure logging from ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    """Run migrations with pgvector type registration.

    Args:
        connection: Database connection object.
    """
    # Register pgvector type so Alembic recognizes Vector columns
    connection.dialect.ischema_names["vector"] = Vector

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode with asyncpg driver."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """Run migrations in offline mode.

    This configures the context with just a URL for generating SQL scripts
    without connecting to the database.
    """
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode using async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
