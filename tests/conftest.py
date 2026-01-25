"""Pytest configuration and shared fixtures for tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Use asyncio backend for async tests.

    Returns:
        Backend name string.
    """
    return "asyncio"


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session.

    Returns:
        AsyncMock configured to simulate database session.
    """
    session = AsyncMock()
    session.execute.return_value = MagicMock()
    return session


@pytest.fixture
def mock_db_session_failing() -> AsyncMock:
    """Create a mock database session that fails on execute.

    Returns:
        AsyncMock configured to raise exception on execute.
    """
    session = AsyncMock()
    session.execute.side_effect = Exception("Database connection failed")
    return session


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis connection that succeeds.

    Returns:
        AsyncMock configured to simulate healthy Redis.
    """
    redis_mock = AsyncMock()
    redis_mock.ping.return_value = True
    return redis_mock


@pytest.fixture
def mock_redis_failing() -> AsyncMock:
    """Create a mock Redis connection that fails.

    Returns:
        AsyncMock configured to raise exception on ping.
    """
    redis_mock = AsyncMock()
    redis_mock.ping.side_effect = Exception("Redis connection refused")
    return redis_mock


@pytest.fixture
def client() -> TestClient:
    """Create a test client for API testing.

    Returns:
        FastAPI TestClient instance.
    """
    return TestClient(app)
