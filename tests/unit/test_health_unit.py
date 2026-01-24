"""Unit tests for health endpoint with mocked dependencies."""

from unittest.mock import AsyncMock, patch

import pytest

from src.api.health import HealthResponse, health_check
from src.core.redis import check_redis_health


@pytest.mark.asyncio
async def test_health_check_all_connected(
    mock_db_session: AsyncMock,
    mock_redis: AsyncMock,
) -> None:
    """Verify health check returns ok when all services are connected."""
    # Arrange
    mock_request = AsyncMock()
    mock_request.app.state.redis = mock_redis

    with patch("src.api.health.get_redis", return_value=mock_redis):
        # Act
        response = await health_check(mock_request, mock_db_session)

    # Assert
    assert isinstance(response, HealthResponse)
    assert response.status == "ok"
    assert response.db == "connected"
    assert response.redis == "connected"


@pytest.mark.asyncio
async def test_health_check_db_disconnected(
    mock_db_session_failing: AsyncMock,
    mock_redis: AsyncMock,
) -> None:
    """Verify health check returns degraded when database is disconnected."""
    # Arrange
    mock_request = AsyncMock()
    mock_request.app.state.redis = mock_redis

    with patch("src.api.health.get_redis", return_value=mock_redis):
        # Act
        response = await health_check(mock_request, mock_db_session_failing)

    # Assert
    assert response.status == "degraded"
    assert response.db == "disconnected"
    assert response.redis == "connected"


@pytest.mark.asyncio
async def test_health_check_redis_disconnected(
    mock_db_session: AsyncMock,
    mock_redis_failing: AsyncMock,
) -> None:
    """Verify health check returns degraded when Redis is disconnected."""
    # Arrange
    mock_request = AsyncMock()
    mock_request.app.state.redis = mock_redis_failing

    with patch("src.api.health.get_redis", return_value=mock_redis_failing):
        # Act
        response = await health_check(mock_request, mock_db_session)

    # Assert
    assert response.status == "degraded"
    assert response.db == "connected"
    assert response.redis == "disconnected"


@pytest.mark.asyncio
async def test_health_check_all_disconnected(
    mock_db_session_failing: AsyncMock,
    mock_redis_failing: AsyncMock,
) -> None:
    """Verify health check returns degraded when all services are down."""
    # Arrange
    mock_request = AsyncMock()
    mock_request.app.state.redis = mock_redis_failing

    with patch("src.api.health.get_redis", return_value=mock_redis_failing):
        # Act
        response = await health_check(mock_request, mock_db_session_failing)

    # Assert
    assert response.status == "degraded"
    assert response.db == "disconnected"
    assert response.redis == "disconnected"


@pytest.mark.asyncio
async def test_check_redis_health_success(mock_redis: AsyncMock) -> None:
    """Verify Redis health check returns True when ping succeeds."""
    result = await check_redis_health(mock_redis)
    assert result is True
    mock_redis.ping.assert_called_once()


@pytest.mark.asyncio
async def test_check_redis_health_failure(mock_redis_failing: AsyncMock) -> None:
    """Verify Redis health check returns False when ping fails."""
    result = await check_redis_health(mock_redis_failing)
    assert result is False
    mock_redis_failing.ping.assert_called_once()
