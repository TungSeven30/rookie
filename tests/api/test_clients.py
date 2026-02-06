"""Tests for clients API endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db
from src.main import app
from src.models.client import Client


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create sqlite-backed session factory for clients API tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Client.__table__.create)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.async_session = factory
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def api_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """Create API client with DB dependency override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_and_get_client(api_client: AsyncClient) -> None:
    """Create client and fetch it by ID."""
    create_response = await api_client.post(
        "/api/clients",
        json={"name": "Alice Walker", "email": "alice@example.com"},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Alice Walker"
    assert created["email"] == "alice@example.com"

    get_response = await api_client.get(f"/api/clients/{created['id']}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == created["id"]
    assert fetched["name"] == "Alice Walker"


@pytest.mark.asyncio
async def test_list_clients_with_search_and_pagination(api_client: AsyncClient) -> None:
    """Search client list and paginate results."""
    await api_client.post("/api/clients", json={"name": "Alice Walker"})
    await api_client.post("/api/clients", json={"name": "Alicia Stone"})
    await api_client.post("/api/clients", json={"name": "Bob Summers"})

    response = await api_client.get("/api/clients", params={"search": "ali", "limit": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert len(payload["items"]) == 1


@pytest.mark.asyncio
async def test_update_client_partial(api_client: AsyncClient) -> None:
    """Patch updates client fields."""
    create_response = await api_client.post(
        "/api/clients",
        json={"name": "Client Name", "email": "old@example.com"},
    )
    client_id = create_response.json()["id"]

    patch_response = await api_client.patch(
        f"/api/clients/{client_id}",
        json={"name": "Updated Name", "email": "new@example.com"},
    )
    assert patch_response.status_code == 200
    payload = patch_response.json()
    assert payload["name"] == "Updated Name"
    assert payload["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_get_client_not_found(api_client: AsyncClient) -> None:
    """Unknown client ID returns 404."""
    response = await api_client.get("/api/clients/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Client not found"

