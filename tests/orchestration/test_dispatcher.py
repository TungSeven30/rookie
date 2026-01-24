"""Tests for task dispatcher."""

import pytest

from src.models.task import Task, TaskStatus

# Import directly from dispatcher module to avoid state_machine import issues
# (state_machine may have broken definitions during parallel plan execution)
from src.orchestration.dispatcher import (
    TaskDispatcher,
    get_dispatcher,
    reset_dispatcher,
)


class TestTaskDispatcher:
    """Tests for TaskDispatcher routing."""

    def setup_method(self) -> None:
        """Reset dispatcher before each test."""
        reset_dispatcher()

    def _create_task(
        self,
        task_type: str = "personal_tax",
        status: TaskStatus = TaskStatus.PENDING,
    ) -> Task:
        """Create a mock task for testing."""
        return Task(
            id=1,
            client_id=1,
            task_type=task_type,
            status=status,
        )

    @pytest.mark.asyncio
    async def test_dispatch_to_registered_handler(self) -> None:
        """Tasks are dispatched to their registered handler."""
        dispatcher = TaskDispatcher()
        calls: list[Task] = []

        async def mock_handler(task: Task) -> None:
            calls.append(task)

        dispatcher.register("personal_tax", mock_handler)
        task = self._create_task(task_type="personal_tax")

        await dispatcher.dispatch(task)

        assert len(calls) == 1
        assert calls[0] is task

    @pytest.mark.asyncio
    async def test_dispatch_unregistered_type_raises(self) -> None:
        """Dispatching unregistered task type raises ValueError."""
        dispatcher = TaskDispatcher()
        task = self._create_task(task_type="unknown_type")

        with pytest.raises(ValueError) as exc_info:
            await dispatcher.dispatch(task)

        assert "No handler registered for task type: unknown_type" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_dispatch_multiple_types(self) -> None:
        """Different task types route to different handlers."""
        dispatcher = TaskDispatcher()
        personal_calls: list[Task] = []
        business_calls: list[Task] = []

        async def personal_handler(task: Task) -> None:
            personal_calls.append(task)

        async def business_handler(task: Task) -> None:
            business_calls.append(task)

        dispatcher.register("personal_tax", personal_handler)
        dispatcher.register("business_tax", business_handler)

        personal_task = self._create_task(task_type="personal_tax")
        business_task = self._create_task(task_type="business_tax")

        await dispatcher.dispatch(personal_task)
        await dispatcher.dispatch(business_task)

        assert len(personal_calls) == 1
        assert personal_calls[0] is personal_task
        assert len(business_calls) == 1
        assert business_calls[0] is business_task

    def test_register_empty_type_raises(self) -> None:
        """Registering empty task type raises ValueError."""
        dispatcher = TaskDispatcher()

        async def mock_handler(task: Task) -> None:
            pass

        with pytest.raises(ValueError) as exc_info:
            dispatcher.register("", mock_handler)

        assert "task_type cannot be empty" in str(exc_info.value)

    def test_register_replaces_existing_handler(self) -> None:
        """Registering same task type replaces handler."""
        dispatcher = TaskDispatcher()

        async def handler1(task: Task) -> None:
            pass

        async def handler2(task: Task) -> None:
            pass

        dispatcher.register("personal_tax", handler1)
        dispatcher.register("personal_tax", handler2)

        # Should have replaced, not added
        assert len(dispatcher.registered_types) == 1
        assert "personal_tax" in dispatcher.registered_types

    def test_is_registered(self) -> None:
        """is_registered returns correct state."""
        dispatcher = TaskDispatcher()

        async def mock_handler(task: Task) -> None:
            pass

        assert not dispatcher.is_registered("personal_tax")

        dispatcher.register("personal_tax", mock_handler)

        assert dispatcher.is_registered("personal_tax")
        assert not dispatcher.is_registered("business_tax")

    def test_unregister_removes_handler(self) -> None:
        """unregister removes registered handler."""
        dispatcher = TaskDispatcher()

        async def mock_handler(task: Task) -> None:
            pass

        dispatcher.register("personal_tax", mock_handler)
        result = dispatcher.unregister("personal_tax")

        assert result is True
        assert not dispatcher.is_registered("personal_tax")

    def test_unregister_nonexistent_returns_false(self) -> None:
        """unregister returns False for nonexistent type."""
        dispatcher = TaskDispatcher()

        result = dispatcher.unregister("nonexistent")

        assert result is False

    def test_registered_types_property(self) -> None:
        """registered_types returns all registered task types."""
        dispatcher = TaskDispatcher()

        async def mock_handler(task: Task) -> None:
            pass

        assert dispatcher.registered_types == []

        dispatcher.register("personal_tax", mock_handler)
        dispatcher.register("business_tax", mock_handler)
        dispatcher.register("bookkeeping", mock_handler)

        types = dispatcher.registered_types
        assert sorted(types) == ["bookkeeping", "business_tax", "personal_tax"]

    @pytest.mark.asyncio
    async def test_handler_exception_propagates(self) -> None:
        """Exceptions from handlers propagate to caller."""
        dispatcher = TaskDispatcher()

        async def failing_handler(task: Task) -> None:
            raise RuntimeError("Handler failed")

        dispatcher.register("personal_tax", failing_handler)
        task = self._create_task(task_type="personal_tax")

        with pytest.raises(RuntimeError) as exc_info:
            await dispatcher.dispatch(task)

        assert "Handler failed" in str(exc_info.value)

    def test_get_dispatcher_singleton(self) -> None:
        """get_dispatcher returns same instance."""
        reset_dispatcher()

        d1 = get_dispatcher()
        d2 = get_dispatcher()

        assert d1 is d2

    def test_reset_dispatcher_clears_singleton(self) -> None:
        """reset_dispatcher creates new instance on next get."""
        d1 = get_dispatcher()
        reset_dispatcher()
        d2 = get_dispatcher()

        assert d1 is not d2
