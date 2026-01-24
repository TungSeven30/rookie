"""Integration tests for health endpoint with live services."""

import os

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from src.main import app

RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS") == "1"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not RUN_INTEGRATION, reason="Set RUN_INTEGRATION_TESTS=1 to enable."
    ),
]


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Create test client with lifespan management."""
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as ac:
            yield ac


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(client: AsyncClient) -> None:
    """Verify health endpoint returns connected status for db and redis."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["redis"] == "connected"
