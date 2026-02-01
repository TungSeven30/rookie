"""Circuit breaker for LLM API calls with Redis-backed state persistence.

Implements the circuit breaker pattern to protect the system from cascading
failures when LLM APIs are unavailable. Uses pybreaker with Redis storage
for state persistence across application restarts.

Configuration:
    - fail_max: 5 consecutive failures to open circuit
    - reset_timeout: 30 seconds before entering half-open state
    - success_threshold: 2 successes in half-open to close circuit
"""

import asyncio
from enum import Enum
from functools import wraps
from typing import Awaitable, Callable, ParamSpec, TypeVar

import pybreaker
import redis
import structlog

logger = structlog.get_logger()

P = ParamSpec("P")
T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, circuit_name: str, state: CircuitState):
        self.circuit_name = circuit_name
        self.state = state
        super().__init__(f"Circuit '{circuit_name}' is {state.value}")


class RedisCircuitBreakerStorage(pybreaker.CircuitBreakerStorage):
    """Redis-backed storage for circuit breaker state.

    Persists circuit breaker state to Redis, allowing state to survive
    application restarts and be shared across multiple instances.
    """

    BASE_NAME = "circuit_breaker"

    def __init__(self, name: str, redis_client: redis.Redis):
        """Initialize Redis storage.

        Args:
            name: Circuit breaker name for namespacing keys
            redis_client: Redis client instance
        """
        self._name = name
        self._redis = redis_client
        self._state_key = f"{self.BASE_NAME}:{name}:state"
        self._counter_key = f"{self.BASE_NAME}:{name}:counter"
        self._opened_at_key = f"{self.BASE_NAME}:{name}:opened_at"

    @property
    def name(self) -> str:
        """Return the name of this storage."""
        return self._name

    @property
    def state(self) -> str:
        """Return the current circuit breaker state."""
        state = self._redis.get(self._state_key)
        if state is None:
            return pybreaker.STATE_CLOSED
        return state.decode("utf-8")

    @state.setter
    def state(self, state: str) -> None:
        """Set the circuit breaker state."""
        self._redis.set(self._state_key, state)

    @property
    def counter(self) -> int:
        """Return the current failure counter."""
        counter = self._redis.get(self._counter_key)
        if counter is None:
            return 0
        return int(counter)

    @counter.setter
    def counter(self, value: int) -> None:
        """Set the failure counter."""
        self._redis.set(self._counter_key, value)

    def increment_counter(self) -> int:
        """Increment the failure counter and return new value."""
        return int(self._redis.incr(self._counter_key))

    @property
    def opened_at(self) -> float | None:
        """Return the timestamp when the circuit was opened."""
        opened_at = self._redis.get(self._opened_at_key)
        if opened_at is None:
            return None
        return float(opened_at)

    @opened_at.setter
    def opened_at(self, value: float | None) -> None:
        """Set the timestamp when the circuit was opened."""
        if value is None:
            self._redis.delete(self._opened_at_key)
        else:
            self._redis.set(self._opened_at_key, value)

    def reset(self) -> None:
        """Reset the circuit breaker state to closed with zero failures."""
        self._redis.delete(self._state_key, self._counter_key, self._opened_at_key)


class CircuitBreaker:
    """Circuit breaker for LLM API calls with Redis persistence.

    Wraps pybreaker.CircuitBreaker with async support and Redis storage.
    Opens after fail_max consecutive failures, enters half-open after
    reset_timeout seconds, and closes after success_threshold successes.

    Usage:
        redis_client = redis.from_url("redis://localhost")
        breaker = CircuitBreaker("openai", redis_client)

        # Using the call method
        result = await breaker.call(my_async_function, arg1, arg2)

        # Using the protect decorator
        @breaker.protect
        async def my_function():
            ...

    Attributes:
        name: Circuit breaker name for identification and Redis keys
        fail_max: Number of consecutive failures before opening
        reset_timeout: Seconds before entering half-open state
        success_threshold: Successes needed in half-open to close
    """

    DEFAULT_FAIL_MAX = 5
    DEFAULT_RESET_TIMEOUT = 30
    DEFAULT_SUCCESS_THRESHOLD = 2

    def __init__(
        self,
        name: str,
        redis_client: redis.Redis,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout: int = DEFAULT_RESET_TIMEOUT,
        success_threshold: int = DEFAULT_SUCCESS_THRESHOLD,
    ):
        """Initialize circuit breaker with Redis storage.

        Args:
            name: Unique name for this circuit breaker
            redis_client: Redis client instance
            fail_max: Consecutive failures to open circuit (default: 5)
            reset_timeout: Seconds before half-open state (default: 30)
            success_threshold: Successes in half-open to close (default: 2)
        """
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.success_threshold = success_threshold
        self._state_cache = CircuitState.CLOSED
        self._failure_count_cache = 0
        self._opened_at_cache: float | None = None

        # Create Redis storage
        self._storage = RedisCircuitBreakerStorage(name, redis_client)

        # Create pybreaker circuit breaker
        self._breaker = pybreaker.CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            state_storage=self._storage,
            listeners=[CircuitBreakerListener(name)],
        )

    @property
    def state(self) -> CircuitState:
        """Return the current circuit state."""
        return self._state_cache

    @property
    def failure_count(self) -> int:
        """Return the current failure count."""
        return self._failure_count_cache

    async def _refresh_state(self) -> None:
        """Refresh cached state from Redis."""
        state_str = await asyncio.to_thread(lambda: self._storage.state)
        self._state_cache = self._normalize_state(state_str)
        self._failure_count_cache = await asyncio.to_thread(lambda: self._storage.counter)
        self._opened_at_cache = await asyncio.to_thread(lambda: self._storage.opened_at)

    def _normalize_state(self, state_str: str) -> CircuitState:
        """Normalize pybreaker state string to CircuitState."""
        if state_str == pybreaker.STATE_CLOSED:
            return CircuitState.CLOSED
        if state_str == pybreaker.STATE_OPEN:
            return CircuitState.OPEN
        if state_str == pybreaker.STATE_HALF_OPEN:
            return CircuitState.HALF_OPEN
        return CircuitState.CLOSED

    async def _set_state(self, state: str) -> None:
        def _set() -> None:
            self._storage.state = state

        await asyncio.to_thread(_set)
        self._state_cache = self._normalize_state(state)

    async def _set_counter(self, value: int) -> None:
        def _set() -> None:
            self._storage.counter = value

        await asyncio.to_thread(_set)
        self._failure_count_cache = value

    async def _increment_counter(self) -> int:
        count = await asyncio.to_thread(self._storage.increment_counter)
        self._failure_count_cache = count
        return count

    async def _set_opened_at(self, value: float | None) -> None:
        def _set() -> None:
            self._storage.opened_at = value

        await asyncio.to_thread(_set)
        self._opened_at_cache = value

    async def call(
        self,
        func: Callable[P, Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Call an async function through the circuit breaker.

        Args:
            func: Async function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            CircuitBreakerError: If the circuit is open
            Exception: Any exception from the wrapped function
        """
        await self._refresh_state()
        if self.state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if not await self._should_try_reset():
                logger.warning(
                    "circuit_breaker_rejected",
                    circuit=self.name,
                    state=self.state.value,
                )
                raise CircuitBreakerError(self.name, self.state)

        try:
            # Attempt the call
            result = await func(*args, **kwargs)

            # Record success
            await self._on_success()

            return result

        except CircuitBreakerError:
            # Re-raise circuit breaker errors
            raise

        except Exception as exc:
            # Record failure
            await self._on_failure()
            raise exc

    async def _should_try_reset(self) -> bool:
        """Check if we should attempt a reset (transition to half-open)."""
        import time

        opened_at = self._opened_at_cache
        if opened_at is None:
            return True

        elapsed = time.time() - opened_at
        if elapsed >= self.reset_timeout:
            # Transition to half-open
            await self._set_state(pybreaker.STATE_HALF_OPEN)
            await self._set_counter(0)  # Reset success counter for half-open
            logger.info(
                "circuit_breaker_half_open",
                circuit=self.name,
                elapsed_seconds=elapsed,
            )
            return True

        return False

    async def _on_success(self) -> None:
        """Handle a successful call."""
        current_state = self.state

        if current_state == CircuitState.HALF_OPEN:
            # Increment success counter in half-open state
            success_count = await self._increment_counter()

            if success_count >= self.success_threshold:
                # Close the circuit
                await self._set_state(pybreaker.STATE_CLOSED)
                await self._set_counter(0)
                await self._set_opened_at(None)
                logger.info(
                    "circuit_breaker_closed",
                    circuit=self.name,
                    success_count=success_count,
                )
        else:
            # Reset failure counter on success in closed state
            await self._set_counter(0)

    async def _on_failure(self) -> None:
        """Handle a failed call."""
        import time

        current_state = self.state

        if current_state == CircuitState.HALF_OPEN:
            # Failure in half-open reopens the circuit
            await self._set_state(pybreaker.STATE_OPEN)
            await self._set_counter(0)
            await self._set_opened_at(time.time())
            logger.warning(
                "circuit_breaker_reopened",
                circuit=self.name,
            )
        else:
            # Increment failure counter in closed state
            failure_count = await self._increment_counter()

            if failure_count >= self.fail_max:
                # Open the circuit
                await self._set_state(pybreaker.STATE_OPEN)
                await self._set_opened_at(time.time())
                logger.warning(
                    "circuit_breaker_opened",
                    circuit=self.name,
                    failure_count=failure_count,
                )

    def protect(
        self, func: Callable[P, Awaitable[T]]
    ) -> Callable[P, Awaitable[T]]:
        """Decorator to protect an async function with this circuit breaker.

        Args:
            func: Async function to protect

        Returns:
            Wrapped async function

        Usage:
            @breaker.protect
            async def my_api_call():
                ...
        """

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await self.call(func, *args, **kwargs)

        return wrapper

    def reset(self) -> None:
        """Reset the circuit breaker to closed state.

        Primarily for testing purposes. Clears all Redis state.
        """
        self._storage.reset()
        self._state_cache = CircuitState.CLOSED
        self._failure_count_cache = 0
        self._opened_at_cache = None
        logger.info(
            "circuit_breaker_reset",
            circuit=self.name,
        )


class CircuitBreakerListener(pybreaker.CircuitBreakerListener):
    """Listener for circuit breaker events for logging."""

    def __init__(self, name: str):
        self.name = name

    def state_change(
        self, cb: pybreaker.CircuitBreaker, old_state: str, new_state: str
    ) -> None:
        """Called when the circuit breaker state changes."""
        logger.info(
            "circuit_breaker_state_change",
            circuit=self.name,
            old_state=old_state,
            new_state=new_state,
        )


# Module-level registry for circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    redis_client: redis.Redis,
    fail_max: int = CircuitBreaker.DEFAULT_FAIL_MAX,
    reset_timeout: int = CircuitBreaker.DEFAULT_RESET_TIMEOUT,
    success_threshold: int = CircuitBreaker.DEFAULT_SUCCESS_THRESHOLD,
) -> CircuitBreaker:
    """Get or create a circuit breaker by name.

    Creates a new circuit breaker if one doesn't exist with the given name.
    Returns the existing instance if it does exist.

    Args:
        name: Unique name for the circuit breaker
        redis_client: Redis client instance
        fail_max: Consecutive failures to open circuit
        reset_timeout: Seconds before half-open state
        success_threshold: Successes in half-open to close

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            redis_client=redis_client,
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            success_threshold=success_threshold,
        )
    return _circuit_breakers[name]


def reset_all_breakers() -> None:
    """Reset all circuit breakers and clear the registry.

    Primarily for testing purposes.
    """
    for breaker in _circuit_breakers.values():
        breaker.reset()
    _circuit_breakers.clear()
    logger.info("all_circuit_breakers_reset")


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitState",
    "RedisCircuitBreakerStorage",
    "get_circuit_breaker",
    "reset_all_breakers",
]
