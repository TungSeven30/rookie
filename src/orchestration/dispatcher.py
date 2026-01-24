"""Task dispatcher for routing tasks to agent handlers.

Provides task_type-based routing to specialized agent handlers.
Each task type (personal_tax, business_tax, bookkeeping) is handled
by a registered async handler function.
"""

from typing import TYPE_CHECKING, Awaitable, Callable

import structlog

if TYPE_CHECKING:
    from src.models.task import Task

logger = structlog.get_logger()

# Type alias for agent handlers
AgentHandler = Callable[["Task"], Awaitable[None]]


class TaskDispatcher:
    """Routes tasks to agent handlers by task_type.

    Usage:
        dispatcher = TaskDispatcher()
        dispatcher.register("personal_tax", personal_tax_agent.handle)
        dispatcher.register("business_tax", business_tax_agent.handle)

        # Later, dispatch a task
        await dispatcher.dispatch(task)  # Routes to correct handler

    Thread Safety:
        Handler registration is not thread-safe. Register all handlers
        at application startup before processing tasks.
    """

    def __init__(self) -> None:
        """Initialize dispatcher with empty handler registry."""
        self._handlers: dict[str, AgentHandler] = {}

    def register(self, task_type: str, handler: AgentHandler) -> None:
        """Register a handler for a task type.

        Args:
            task_type: Task type identifier (e.g., "personal_tax")
            handler: Async function that processes tasks of this type

        Raises:
            ValueError: If task_type is empty
        """
        if not task_type:
            raise ValueError("task_type cannot be empty")

        if task_type in self._handlers:
            logger.warning(
                "handler_replaced",
                task_type=task_type,
                message="Replacing existing handler for task type",
            )

        self._handlers[task_type] = handler
        logger.info(
            "handler_registered",
            task_type=task_type,
        )

    def unregister(self, task_type: str) -> bool:
        """Unregister a handler for a task type.

        Args:
            task_type: Task type to unregister

        Returns:
            True if handler was removed, False if not found
        """
        if task_type in self._handlers:
            del self._handlers[task_type]
            logger.info(
                "handler_unregistered",
                task_type=task_type,
            )
            return True
        return False

    def is_registered(self, task_type: str) -> bool:
        """Check if a handler is registered for a task type.

        Args:
            task_type: Task type to check

        Returns:
            True if handler is registered
        """
        return task_type in self._handlers

    @property
    def registered_types(self) -> list[str]:
        """Get list of registered task types."""
        return list(self._handlers.keys())

    async def dispatch(self, task: "Task") -> None:
        """Dispatch a task to its registered handler.

        Args:
            task: Task to dispatch

        Raises:
            ValueError: If no handler registered for task's task_type
        """
        handler = self._handlers.get(task.task_type)

        if handler is None:
            logger.error(
                "dispatch_failed",
                task_id=task.id,
                task_type=task.task_type,
                registered_types=self.registered_types,
                message="No handler registered for task type",
            )
            raise ValueError(
                f"No handler registered for task type: {task.task_type}"
            )

        logger.info(
            "task_dispatched",
            task_id=task.id,
            task_type=task.task_type,
        )

        await handler(task)

        logger.info(
            "task_handler_completed",
            task_id=task.id,
            task_type=task.task_type,
        )


# Module-level singleton for convenience (optional usage pattern)
_default_dispatcher: TaskDispatcher | None = None


def get_dispatcher() -> TaskDispatcher:
    """Get or create the default task dispatcher singleton.

    Returns:
        The default TaskDispatcher instance
    """
    global _default_dispatcher
    if _default_dispatcher is None:
        _default_dispatcher = TaskDispatcher()
    return _default_dispatcher


def reset_dispatcher() -> None:
    """Reset the default dispatcher. Primarily for testing."""
    global _default_dispatcher
    _default_dispatcher = None


__all__ = [
    "TaskDispatcher",
    "AgentHandler",
    "get_dispatcher",
    "reset_dispatcher",
]
