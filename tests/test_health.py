"""Unit tests for health endpoint behavior."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_db
from src.main import app


class FakeSession:
    """Fake async database session for health checks."""

    def __init__(self, should_fail: bool) -> None:
        self.should_fail = should_fail

    async def execute(self, _statement: object) -> None:
        """Simulate database execute behavior."""
        if self.should_fail:
            raise RuntimeError("database unavailable")


class FakeRedis:
    """Fake Redis client for health checks."""

    def __init__(self, should_fail: bool) -> None:
        self.should_fail = should_fail

    async def ping(self) -> bool:
        """Simulate Redis ping."""
        if self.should_fail:
            raise RuntimeError("redis unavailable")
        return True


async def _make_request(
    db_fail: bool = False, redis_fail: bool = False
) -> AsyncClient:
    async def override_get_db() -> AsyncGenerator[FakeSession, None]:
        yield FakeSession(should_fail=db_fail)

    app.dependency_overrides[get_db] = override_get_db
    app.state.redis = FakeRedis(should_fail=redis_fail)

    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok() -> None:
    """Return ok when db and redis are connected."""
    client = await _make_request()
    try:
        response = await client.get("/api/health")
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["redis"] == "connected"


@pytest.mark.asyncio
async def test_health_endpoint_degraded_on_db_failure() -> None:
    """Return degraded when database is disconnected."""
    client = await _make_request(db_fail=True)
    try:
        response = await client.get("/api/health")
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["db"] == "disconnected"
    assert data["redis"] == "connected"


@pytest.mark.asyncio
async def test_health_endpoint_degraded_on_redis_failure() -> None:
    """Return degraded when Redis is disconnected."""
    client = await _make_request(redis_fail=True)
    try:
        response = await client.get("/api/health")
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["db"] == "connected"
    assert data["redis"] == "disconnected"


@pytest.mark.asyncio
async def test_health_endpoint_schema() -> None:
    """Verify health endpoint response matches expected schema."""
    client = await _make_request()
    try:
        response = await client.get("/api/health")
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    data = response.json()
    assert set(data.keys()) == {"status", "db", "redis"}
    assert all(isinstance(v, str) for v in data.values())
