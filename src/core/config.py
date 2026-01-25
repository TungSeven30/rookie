"""Application configuration using Pydantic Settings."""

from pydantic import field_validator
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

    anthropic_api_key: str | None = None
    """Anthropic API key for document extraction."""

    # Environment
    environment: str = "development"
    """Current environment (development, staging, production)."""

    debug: bool = False
    """Enable debug mode."""

    log_format: str | None = None
    """Logging format override (json or console). Defaults by environment."""

    # Demo API
    demo_api_key: str | None = None
    """API key required for demo endpoints (X-Demo-Api-Key)."""

    default_storage_url: str = "/tmp/storage"
    """Default storage URL for uploads (file://, s3://, gs://, or local)."""

    output_dir: str = "/tmp/output"
    """Default output directory for generated artifacts."""

    max_upload_bytes: int = 50 * 1024 * 1024
    """Maximum upload size in bytes for demo files."""

    allowed_upload_types: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/jpg",
    ]
    """Allowed content types for demo uploads."""

    demo_retention_days: int = 7
    """Retention period for demo uploads and artifacts."""

    @field_validator("allowed_upload_types", mode="before")
    @classmethod
    def parse_allowed_upload_types(cls, value: object) -> list[str]:
        """Parse allowed upload types from CSV or list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/jpg",
        ]


settings = Settings()
