"""Structured logging configuration using structlog."""

import logging
import sys
from contextvars import ContextVar
from typing import Any

import orjson
import structlog
from structlog.types import Processor

from src.core.config import settings

# Context variables for request/task correlation
task_id_ctx: ContextVar[str | None] = ContextVar("task_id", default=None)
client_id_ctx: ContextVar[str | None] = ContextVar("client_id", default=None)
agent_ctx: ContextVar[str | None] = ContextVar("agent", default=None)


def _add_context_vars(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add context variables to log events.

    Args:
        logger: The logger instance (unused).
        method_name: The logging method name (unused).
        event_dict: The log event dictionary.

    Returns:
        Updated event dictionary with context variables.
    """
    if task_id := task_id_ctx.get():
        event_dict["task_id"] = task_id
    if client_id := client_id_ctx.get():
        event_dict["client_id"] = client_id
    if agent := agent_ctx.get():
        event_dict["agent"] = agent
    return event_dict


def _orjson_serializer(obj: Any, **kwargs: Any) -> str:
    """Serialize log event to JSON using orjson.

    Args:
        obj: Object to serialize.
        **kwargs: Additional keyword arguments (unused).

    Returns:
        JSON string representation.
    """
    return orjson.dumps(obj).decode("utf-8")


def configure_logging() -> None:
    """Configure structlog for the application.

    Development mode: ConsoleRenderer with colors for readability.
    Production mode: JSONRenderer with orjson for structured logging.
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _add_context_vars,
    ]

    log_format = settings.log_format.lower() if settings.log_format else None
    use_json = log_format == "json" or (
        log_format is None and settings.environment != "development"
    )

    if use_json:
        # JSON output with explicit message field for observability tooling.
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.EventRenamer("message"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(serializer=_orjson_serializer),
        ]
    else:
        # Development: colored console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to route through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.debug else logging.INFO,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured structlog logger.

    Args:
        name: Optional logger name. Defaults to __name__ of caller.

    Returns:
        Configured structlog bound logger.
    """
    return structlog.get_logger(name)
