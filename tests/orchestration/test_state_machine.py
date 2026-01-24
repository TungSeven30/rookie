"""Tests for task state machine."""

import pytest
from statemachine.exceptions import TransitionNotAllowed

from src.models.task import Task, TaskStatus
from src.orchestration.state_machine import (
    TaskStateMachine,
    create_state_machine,
)


class TestTaskStateMachine:
    """Tests for TaskStateMachine transitions."""

    def _create_task(self, status: TaskStatus = TaskStatus.PENDING) -> Task:
        """Create a mock task for testing.

        Args:
            status: Initial task status

        Returns:
            Task instance with minimal required fields
        """
        task = Task(
            id=1,
            client_id=1,
            task_type="personal_tax",
            status=status,
        )
        return task

    def test_initial_state_from_pending_task(self) -> None:
        """State machine starts in pending state for pending task."""
        task = self._create_task(TaskStatus.PENDING)
        sm = TaskStateMachine(task=task)

        assert sm.current_state == sm.pending
        assert sm.get_state_value() == TaskStatus.PENDING

    def test_initial_state_from_in_progress_task(self) -> None:
        """State machine starts in correct state for non-pending task."""
        task = self._create_task(TaskStatus.IN_PROGRESS)
        task.assigned_agent = "personal_tax_agent"
        sm = TaskStateMachine(task=task)

        assert sm.current_state == sm.in_progress
        assert sm.get_state_value() == TaskStatus.IN_PROGRESS

    def test_assign_transition(self) -> None:
        """Transition from pending to assigned."""
        task = self._create_task()
        sm = TaskStateMachine(task=task)

        sm.assign(agent="personal_tax_agent")

        assert sm.current_state == sm.assigned
        assert task.status == TaskStatus.ASSIGNED
        assert task.assigned_agent == "personal_tax_agent"

    def test_start_transition(self) -> None:
        """Transition from assigned to in_progress."""
        task = self._create_task(TaskStatus.ASSIGNED)
        task.assigned_agent = "personal_tax_agent"
        sm = TaskStateMachine(task=task)

        sm.start()

        assert sm.current_state == sm.in_progress
        assert task.status == TaskStatus.IN_PROGRESS

    def test_complete_transition(self) -> None:
        """Transition from in_progress to completed."""
        task = self._create_task(TaskStatus.IN_PROGRESS)
        task.assigned_agent = "personal_tax_agent"
        sm = TaskStateMachine(task=task)

        sm.complete()

        assert sm.current_state == sm.completed
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_fail_from_in_progress(self) -> None:
        """Transition from in_progress to failed."""
        task = self._create_task(TaskStatus.IN_PROGRESS)
        task.assigned_agent = "personal_tax_agent"
        sm = TaskStateMachine(task=task)

        sm.fail(reason="LLM API error")

        assert sm.current_state == sm.failed
        assert task.status == TaskStatus.FAILED

    def test_fail_from_assigned(self) -> None:
        """Transition from assigned to failed."""
        task = self._create_task(TaskStatus.ASSIGNED)
        task.assigned_agent = "personal_tax_agent"
        sm = TaskStateMachine(task=task)

        sm.fail(reason="Agent unavailable")

        assert sm.current_state == sm.failed
        assert task.status == TaskStatus.FAILED

    def test_escalate_from_in_progress(self) -> None:
        """Transition from in_progress to escalated."""
        task = self._create_task(TaskStatus.IN_PROGRESS)
        task.assigned_agent = "personal_tax_agent"
        sm = TaskStateMachine(task=task)

        sm.escalate(reason="Missing W-2 document")

        assert sm.current_state == sm.escalated
        assert task.status == TaskStatus.ESCALATED

    def test_escalate_from_assigned(self) -> None:
        """Transition from assigned to escalated."""
        task = self._create_task(TaskStatus.ASSIGNED)
        task.assigned_agent = "personal_tax_agent"
        sm = TaskStateMachine(task=task)

        sm.escalate(reason="Client data inconsistency")

        assert sm.current_state == sm.escalated
        assert task.status == TaskStatus.ESCALATED

    def test_retry_from_failed(self) -> None:
        """Transition from failed back to pending for retry."""
        task = self._create_task(TaskStatus.FAILED)
        task.assigned_agent = "personal_tax_agent"
        sm = TaskStateMachine(task=task)

        sm.retry()

        assert sm.current_state == sm.pending
        assert task.status == TaskStatus.PENDING
        assert task.assigned_agent is None
        assert task.completed_at is None

    def test_invalid_transition_pending_to_completed(self) -> None:
        """Cannot transition directly from pending to completed."""
        task = self._create_task(TaskStatus.PENDING)
        sm = TaskStateMachine(task=task)

        with pytest.raises(TransitionNotAllowed):
            sm.complete()

    def test_invalid_transition_pending_to_in_progress(self) -> None:
        """Cannot transition directly from pending to in_progress."""
        task = self._create_task(TaskStatus.PENDING)
        sm = TaskStateMachine(task=task)

        with pytest.raises(TransitionNotAllowed):
            sm.start()

    def test_invalid_transition_from_completed(self) -> None:
        """Cannot transition from completed (final state)."""
        task = self._create_task(TaskStatus.COMPLETED)
        sm = TaskStateMachine(task=task)

        with pytest.raises(TransitionNotAllowed):
            sm.retry()

    def test_invalid_transition_from_escalated(self) -> None:
        """Cannot transition from escalated (final state)."""
        task = self._create_task(TaskStatus.ESCALATED)
        sm = TaskStateMachine(task=task)

        with pytest.raises(TransitionNotAllowed):
            sm.retry()

    def test_full_happy_path(self) -> None:
        """Test complete successful workflow."""
        task = self._create_task()
        sm = TaskStateMachine(task=task)

        # Full workflow: pending -> assigned -> in_progress -> completed
        sm.assign(agent="personal_tax_agent")
        sm.start()
        sm.complete()

        assert task.status == TaskStatus.COMPLETED
        assert task.assigned_agent == "personal_tax_agent"
        assert task.completed_at is not None

    def test_fail_and_retry_path(self) -> None:
        """Test failure with retry workflow."""
        task = self._create_task()
        sm = TaskStateMachine(task=task)

        # Workflow: pending -> assigned -> in_progress -> failed -> pending
        sm.assign(agent="personal_tax_agent")
        sm.start()
        sm.fail(reason="Temporary error")
        sm.retry()

        assert task.status == TaskStatus.PENDING
        assert task.assigned_agent is None

    def test_create_state_machine_factory(self) -> None:
        """Test factory function creates correct state machine."""
        task = self._create_task(TaskStatus.ASSIGNED)
        task.assigned_agent = "test_agent"

        sm = create_state_machine(task=task)

        assert isinstance(sm, TaskStateMachine)
        assert sm.current_state == sm.assigned
        assert sm.task is task
