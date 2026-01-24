"""Task state machine for orchestration.

Provides declarative state transitions for tasks with callbacks
for side effects (database updates, logging, metrics).
"""

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from statemachine import State, StateMachine
from statemachine.exceptions import TransitionNotAllowed

from src.models.task import TaskStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.models.task import Task

logger = structlog.get_logger()


class TaskStateMachine(StateMachine):
    """State machine for task lifecycle management.

    States match TaskStatus enum from models:
    - pending: Task created, awaiting assignment
    - assigned: Task assigned to an agent
    - in_progress: Agent actively working on task
    - completed: Task finished successfully (final)
    - failed: Task failed, may retry (not final to allow retry transition)
    - escalated: Task requires human intervention (final)

    Transitions:
    - assign: pending -> assigned
    - start: assigned -> in_progress
    - complete: in_progress -> completed
    - fail: in_progress/assigned -> failed
    - escalate: in_progress/assigned -> escalated
    - retry: failed -> pending (allows retry after failure)

    Usage:
        task = Task(status=TaskStatus.PENDING, ...)
        sm = TaskStateMachine(task=task)
        sm.assign(agent="personal_tax_agent")
        sm.start()
        sm.complete()
    """

    # States (match TaskStatus enum values)
    pending = State(initial=True, value=TaskStatus.PENDING)
    assigned = State(value=TaskStatus.ASSIGNED)
    in_progress = State(value=TaskStatus.IN_PROGRESS)
    completed = State(final=True, value=TaskStatus.COMPLETED)
    failed = State(value=TaskStatus.FAILED)  # Not final - allows retry transition
    escalated = State(final=True, value=TaskStatus.ESCALATED)

    # Transitions
    assign = pending.to(assigned)
    start = assigned.to(in_progress)
    complete = in_progress.to(completed)
    fail = in_progress.to(failed) | assigned.to(failed)
    escalate = in_progress.to(escalated) | assigned.to(escalated)
    retry = failed.to(pending)

    def __init__(
        self,
        task: "Task",
        session: "AsyncSession | None" = None,
    ) -> None:
        """Initialize state machine for a task.

        Args:
            task: Task model instance to manage
            session: Optional SQLAlchemy session for persistence
        """
        self.task = task
        self.session = session
        # Initialize state machine using task's status field
        # The model parameter binds to task, state_field reads/writes task.status
        # start_value ensures we start from the task's current status
        super().__init__(
            model=task,
            state_field="status",
            start_value=task.status,
        )

    def get_state_value(self) -> TaskStatus:
        """Get current state as TaskStatus enum.

        Returns:
            Current TaskStatus value
        """
        return self.current_state.value

    # Transition callbacks
    def on_assign(self, agent: str) -> None:
        """Called when task is assigned to an agent.

        Args:
            agent: Name/identifier of the assigned agent
        """
        self.task.assigned_agent = agent
        logger.info(
            "task_assigned",
            task_id=self.task.id,
            agent=agent,
        )

    def on_start(self) -> None:
        """Called when agent starts working on task."""
        logger.info(
            "task_started",
            task_id=self.task.id,
            agent=self.task.assigned_agent,
        )

    def on_complete(self) -> None:
        """Called when task completes successfully."""
        self.task.completed_at = datetime.utcnow()
        logger.info(
            "task_completed",
            task_id=self.task.id,
            agent=self.task.assigned_agent,
        )

    def on_fail(self, reason: str = "") -> None:
        """Called when task fails.

        Args:
            reason: Description of failure
        """
        logger.warning(
            "task_failed",
            task_id=self.task.id,
            agent=self.task.assigned_agent,
            reason=reason,
        )

    def on_escalate(self, reason: str = "") -> None:
        """Called when task is escalated to human.

        Args:
            reason: Description of why escalation needed
        """
        logger.warning(
            "task_escalated",
            task_id=self.task.id,
            agent=self.task.assigned_agent,
            reason=reason,
        )

    def on_retry(self) -> None:
        """Called when retrying a failed task."""
        self.task.assigned_agent = None
        self.task.completed_at = None
        logger.info(
            "task_retry",
            task_id=self.task.id,
        )


def create_state_machine(
    task: "Task",
    session: "AsyncSession | None" = None,
) -> TaskStateMachine:
    """Factory function to create state machine for a task.

    Args:
        task: Task model instance
        session: Optional SQLAlchemy session

    Returns:
        TaskStateMachine initialized from task's current state
    """
    return TaskStateMachine(task=task, session=session)


__all__ = [
    "TaskStateMachine",
    "TransitionNotAllowed",
    "create_state_machine",
]
