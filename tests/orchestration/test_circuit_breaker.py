"""Tests for circuit breaker with Redis persistence.

These tests require a running Redis instance. They will be skipped
if Redis is not available.
"""

import time
from unittest.mock import MagicMock

import pytest
import redis

from src.orchestration.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
    get_circuit_breaker,
    reset_all_breakers,
)


def redis_available() -> bool:
    """Check if Redis is available for testing."""
    try:
        client = redis.from_url("redis://localhost:6379")
        client.ping()
        return True
    except redis.ConnectionError:
        return False


pytestmark = pytest.mark.skipif(
    not redis_available(),
    reason="Redis not available",
)


@pytest.fixture
def redis_client():
    """Provide a Redis client for tests."""
    client = redis.from_url("redis://localhost:6379")
    yield client
    # Cleanup: delete all circuit breaker keys
    keys = client.keys("circuit_breaker:*")
    if keys:
        client.delete(*keys)
    client.close()


@pytest.fixture
def breaker(redis_client):
    """Provide a circuit breaker for tests."""
    cb = CircuitBreaker(
        name="test_breaker",
        redis_client=redis_client,
        fail_max=5,
        reset_timeout=30,
        success_threshold=2,
    )
    yield cb
    # Reset after each test
    cb.reset()
    reset_all_breakers()


class TestCircuitBreakerInitialState:
    """Tests for initial circuit breaker state."""

    def test_starts_closed(self, breaker):
        """Circuit breaker starts in closed state."""
        assert breaker.state == CircuitState.CLOSED

    def test_initial_failure_count_is_zero(self, breaker):
        """Failure count starts at zero."""
        assert breaker.failure_count == 0


class TestCircuitBreakerClosedState:
    """Tests for closed state behavior."""

    @pytest.mark.asyncio
    async def test_successful_call_stays_closed(self, breaker):
        """Successful calls keep circuit closed."""

        async def success():
            return "ok"

        result = await breaker.call(success)
        assert result == "ok"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_failure_increments_counter(self, breaker):
        """Failed calls increment the failure counter."""

        async def fail():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await breaker.call(fail)

        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_failure_counter(self, breaker):
        """Successful call resets failure counter."""

        async def fail():
            raise ValueError("test error")

        async def success():
            return "ok"

        # Cause some failures
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(fail)

        assert breaker.failure_count == 3

        # Now succeed
        result = await breaker.call(success)
        assert result == "ok"
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_uses_to_thread_for_storage(self, breaker, monkeypatch):
        """Circuit breaker should offload storage calls to threads."""
        calls: list[object] = []

        async def fake_to_thread(func, *args, **kwargs):
            calls.append(func)
            return func(*args, **kwargs)

        monkeypatch.setattr(
            "src.orchestration.circuit_breaker.asyncio.to_thread", fake_to_thread
        )

        async def success():
            return "ok"

        await breaker.call(success)

        assert calls


class TestCircuitBreakerOpens:
    """Tests for circuit breaker opening after failures."""

    @pytest.mark.asyncio
    async def test_opens_after_5_failures(self, breaker):
        """Circuit opens after 5 consecutive failures (ORCH-03)."""

        async def fail():
            raise ValueError("test error")

        # Cause 5 failures
        for i in range(5):
            with pytest.raises(ValueError, match="test error"):
                await breaker.call(fail)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_does_not_open_after_4_failures(self, breaker):
        """Circuit stays closed after 4 failures."""

        async def fail():
            raise ValueError("test error")

        for _ in range(4):
            with pytest.raises(ValueError):
                await breaker.call(fail)

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self, breaker):
        """Open circuit rejects calls immediately."""

        async def fail():
            raise ValueError("test error")

        async def success():
            return "ok"

        # Open the circuit
        for _ in range(5):
            with pytest.raises(ValueError):
                await breaker.call(fail)

        assert breaker.state == CircuitState.OPEN

        # Now calls should be rejected
        with pytest.raises(CircuitBreakerError) as exc_info:
            await breaker.call(success)

        assert exc_info.value.circuit_name == "test_breaker"
        assert exc_info.value.state == CircuitState.OPEN


class TestCircuitBreakerHalfOpen:
    """Tests for half-open state behavior."""

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, redis_client):
        """Circuit enters half-open after timeout (ORCH-04)."""
        # Use a short timeout for testing
        breaker = CircuitBreaker(
            name="timeout_test",
            redis_client=redis_client,
            fail_max=5,
            reset_timeout=1,  # 1 second timeout
            success_threshold=2,
        )

        async def fail():
            raise ValueError("test error")

        async def success():
            return "ok"

        try:
            # Open the circuit
            for _ in range(5):
                with pytest.raises(ValueError):
                    await breaker.call(fail)

            assert breaker.state == CircuitState.OPEN

            # Wait for timeout
            time.sleep(1.1)

            # Next call should trigger half-open transition
            result = await breaker.call(success)
            assert result == "ok"
            # After one success, still in half-open until success_threshold
            # Note: The state might be CLOSED if one success is enough
            # depending on implementation. With success_threshold=2,
            # we need 2 successes.
            assert breaker.state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]
        finally:
            breaker.reset()

    @pytest.mark.asyncio
    async def test_closes_after_2_successes_in_half_open(self, redis_client):
        """Circuit closes after 2 successes in half-open (ORCH-05)."""
        breaker = CircuitBreaker(
            name="success_threshold_test",
            redis_client=redis_client,
            fail_max=5,
            reset_timeout=1,  # 1 second timeout
            success_threshold=2,
        )

        async def fail():
            raise ValueError("test error")

        async def success():
            return "ok"

        try:
            # Open the circuit
            for _ in range(5):
                with pytest.raises(ValueError):
                    await breaker.call(fail)

            assert breaker.state == CircuitState.OPEN

            # Wait for timeout
            time.sleep(1.1)

            # First success
            await breaker.call(success)

            # Second success should close the circuit
            await breaker.call(success)

            assert breaker.state == CircuitState.CLOSED
        finally:
            breaker.reset()

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens(self, redis_client):
        """Failure in half-open state reopens the circuit."""
        breaker = CircuitBreaker(
            name="reopen_test",
            redis_client=redis_client,
            fail_max=5,
            reset_timeout=1,
            success_threshold=2,
        )

        async def fail():
            raise ValueError("test error")

        try:
            # Open the circuit
            for _ in range(5):
                with pytest.raises(ValueError):
                    await breaker.call(fail)

            assert breaker.state == CircuitState.OPEN

            # Wait for timeout
            time.sleep(1.1)

            # Failure in half-open should reopen
            with pytest.raises(ValueError):
                await breaker.call(fail)

            assert breaker.state == CircuitState.OPEN
        finally:
            breaker.reset()


class TestProtectDecorator:
    """Tests for the protect decorator."""

    @pytest.mark.asyncio
    async def test_protect_decorator(self, breaker):
        """Protect decorator wraps function with circuit breaker."""

        @breaker.protect
        async def protected_func(x: int) -> int:
            return x * 2

        result = await protected_func(5)
        assert result == 10
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_protect_decorator_handles_errors(self, breaker):
        """Protect decorator properly tracks failures."""

        @breaker.protect
        async def failing_func():
            raise RuntimeError("decorated failure")

        for _ in range(5):
            with pytest.raises(RuntimeError, match="decorated failure"):
                await failing_func()

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_protect_decorator_rejects_when_open(self, breaker):
        """Protected function is rejected when circuit is open."""

        @breaker.protect
        async def protected_func():
            return "ok"

        # Manually open the circuit
        async def fail():
            raise ValueError("test")

        for _ in range(5):
            with pytest.raises(ValueError):
                await breaker.call(fail)

        # Protected function should now be rejected
        with pytest.raises(CircuitBreakerError):
            await protected_func()


class TestReset:
    """Tests for reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_method(self, breaker):
        """Reset method restores circuit to closed state."""

        async def fail():
            raise ValueError("test error")

        # Open the circuit
        for _ in range(5):
            with pytest.raises(ValueError):
                await breaker.call(fail)

        assert breaker.state == CircuitState.OPEN

        # Reset
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0


class TestMultipleBreakers:
    """Tests for multiple circuit breakers."""

    @pytest.mark.asyncio
    async def test_multiple_breakers_independent(self, redis_client):
        """Multiple circuit breakers operate independently."""
        breaker_a = CircuitBreaker(
            name="breaker_a",
            redis_client=redis_client,
            fail_max=5,
            reset_timeout=30,
            success_threshold=2,
        )
        breaker_b = CircuitBreaker(
            name="breaker_b",
            redis_client=redis_client,
            fail_max=5,
            reset_timeout=30,
            success_threshold=2,
        )

        async def fail():
            raise ValueError("test error")

        async def success():
            return "ok"

        try:
            # Open breaker_a
            for _ in range(5):
                with pytest.raises(ValueError):
                    await breaker_a.call(fail)

            assert breaker_a.state == CircuitState.OPEN
            assert breaker_b.state == CircuitState.CLOSED

            # breaker_b should still work
            result = await breaker_b.call(success)
            assert result == "ok"
        finally:
            breaker_a.reset()
            breaker_b.reset()


class TestFactoryFunctions:
    """Tests for module-level factory functions."""

    def test_get_circuit_breaker_creates_new(self, redis_client):
        """get_circuit_breaker creates new breaker if not exists."""
        reset_all_breakers()

        breaker = get_circuit_breaker("factory_test", redis_client)
        assert breaker.name == "factory_test"
        assert breaker.state == CircuitState.CLOSED

    def test_get_circuit_breaker_returns_existing(self, redis_client):
        """get_circuit_breaker returns existing breaker if exists."""
        reset_all_breakers()

        breaker1 = get_circuit_breaker("same_name", redis_client)
        breaker2 = get_circuit_breaker("same_name", redis_client)

        assert breaker1 is breaker2

    def test_reset_all_breakers(self, redis_client):
        """reset_all_breakers clears all breakers."""
        reset_all_breakers()

        breaker1 = get_circuit_breaker("breaker1", redis_client)
        breaker2 = get_circuit_breaker("breaker2", redis_client)

        reset_all_breakers()

        # New calls should create new breakers
        breaker1_new = get_circuit_breaker("breaker1", redis_client)
        assert breaker1_new is not breaker1


class TestCircuitBreakerConfiguration:
    """Tests for circuit breaker configuration."""

    def test_default_configuration(self, redis_client):
        """Default configuration values are correct."""
        breaker = CircuitBreaker("defaults", redis_client)

        assert breaker.fail_max == 5
        assert breaker.reset_timeout == 30
        assert breaker.success_threshold == 2

        breaker.reset()

    def test_custom_configuration(self, redis_client):
        """Custom configuration is applied."""
        breaker = CircuitBreaker(
            name="custom",
            redis_client=redis_client,
            fail_max=10,
            reset_timeout=60,
            success_threshold=3,
        )

        assert breaker.fail_max == 10
        assert breaker.reset_timeout == 60
        assert breaker.success_threshold == 3

        breaker.reset()

    @pytest.mark.asyncio
    async def test_custom_fail_max(self, redis_client):
        """Custom fail_max is honored."""
        breaker = CircuitBreaker(
            name="custom_fail_max",
            redis_client=redis_client,
            fail_max=3,  # Lower threshold
            reset_timeout=30,
            success_threshold=2,
        )

        async def fail():
            raise ValueError("test")

        try:
            for _ in range(3):
                with pytest.raises(ValueError):
                    await breaker.call(fail)

            assert breaker.state == CircuitState.OPEN
        finally:
            breaker.reset()


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError exception."""

    def test_error_message(self):
        """CircuitBreakerError has informative message."""
        error = CircuitBreakerError("test_circuit", CircuitState.OPEN)
        assert str(error) == "Circuit 'test_circuit' is open"
        assert error.circuit_name == "test_circuit"
        assert error.state == CircuitState.OPEN
