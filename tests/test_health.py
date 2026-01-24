"""Integration tests for health endpoint."""

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest_asyncio.fixture
async def client():
    """Create test client with lifespan management."""
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as ac:
            yield ac


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(client: AsyncClient):
    """Verify health endpoint returns connected status for db and redis."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["redis"] == "connected"


@pytest.mark.asyncio
async def test_health_endpoint_schema(client: AsyncClient):
    """Verify health endpoint response matches expected schema."""
    response = await client.get("/api/health")

    data = response.json()
    assert set(data.keys()) == {"status", "db", "redis"}
    assert all(isinstance(v, str) for v in data.values())
