"""Application configuration using Pydantic Settings."""

import json
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    openai_api_key: str | None = None
    """OpenAI API key for document extraction when using OpenAI vision."""

    anthropic_model: str = "claude-3-5-sonnet-20241022"
    """Model used by the document vision pipeline.

    Aliases are supported via `resolve_vision_model` and map to provider/model:
    - `opus-4.6` (or `opus`) -> Anthropic (`claude-opus-4-6`)
    - `gpt-5.3` (or `gpt`) -> OpenAI
    """

    document_processing_concurrency: int = 2
    """Max concurrent document pages to classify/extract."""

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

    # NoDecode prevents pydantic-settings from forcing JSON parsing at the
    # env-source layer, so we can accept either JSON arrays or CSV strings.
    allowed_upload_types: Annotated[list[str], NoDecode] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/jpg",
    ]
    """Allowed content types for demo uploads."""

    demo_retention_days: int = 7
    """Retention period for demo uploads and artifacts."""

    taxdome_webhook_secret: str | None = None
    """Optional shared secret for validating TaxDome webhook calls."""

    @field_validator("allowed_upload_types", mode="before")
    @classmethod
    def parse_allowed_upload_types(cls, value: object) -> list[str]:
        """Parse allowed upload types from JSON array, CSV, or list."""
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return [
                    "application/pdf",
                    "image/jpeg",
                    "image/png",
                    "image/jpg",
                ]

            # Try JSON first so values like:
            #   ["application/pdf","image/jpeg"]
            # are accepted from .env.
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                decoded = None

            if isinstance(decoded, list):
                return [str(item).strip() for item in decoded if str(item).strip()]
            if isinstance(decoded, str):
                text = decoded

            # Fallback: comma-separated values
            return [item.strip() for item in text.split(",") if item.strip()]

        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/jpg",
        ]


settings = Settings()
