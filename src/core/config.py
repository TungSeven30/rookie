"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str
    """PostgreSQL connection URL (asyncpg driver)."""

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    """Redis connection URL for job queue and caching."""

    # Error Tracking
    sentry_dsn: str | None = None
    """Sentry DSN for error tracking. Optional."""

    # Environment
    environment: str = "development"
    """Current environment (development, staging, production)."""

    debug: bool = False
    """Enable debug mode."""

    log_format: str | None = None
    """Logging format override (json or console). Defaults by environment."""


settings = Settings()
