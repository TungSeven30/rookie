"""Tests for structured logging configuration."""

import structlog

from src.core.config import settings
from src.core.logging import configure_logging


def _reset_structlog() -> None:
    """Reset structlog defaults to avoid test cross-talk."""
    structlog.reset_defaults()


def test_configure_logging_uses_json_when_log_format_json() -> None:
    """Use JSON logging when log_format=json, even in development."""
    original_env = settings.environment
    original_format = getattr(settings, "log_format", None)

    try:
        settings.environment = "development"
        settings.log_format = "json"
        configure_logging()

        processors = structlog.get_config()["processors"]
        assert any(
            isinstance(processor, structlog.processors.JSONRenderer)
            for processor in processors
        )
        assert any(
            isinstance(processor, structlog.processors.EventRenamer)
            for processor in processors
        )
    finally:
        settings.environment = original_env
        settings.log_format = original_format
        _reset_structlog()


def test_configure_logging_uses_console_when_log_format_console() -> None:
    """Use console logging when log_format=console in development."""
    original_env = settings.environment
    original_format = getattr(settings, "log_format", None)

    try:
        settings.environment = "development"
        settings.log_format = "console"
        configure_logging()

        processors = structlog.get_config()["processors"]
        assert any(
            isinstance(processor, structlog.dev.ConsoleRenderer)
            for processor in processors
        )
        assert not any(
            isinstance(processor, structlog.processors.JSONRenderer)
            for processor in processors
        )
    finally:
        settings.environment = original_env
        settings.log_format = original_format
        _reset_structlog()
