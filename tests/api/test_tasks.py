"""Tests for tasks API endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db
from src.main import app
from src.models.client import Client
from src.models.task import Escalation, Task


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create sqlite-backed session factory for tasks API tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Client.__table__.create)
        await conn.run_sync(Task.__table__.create)
        await conn.run_sync(Escalation.__table__.create)

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


async def _create_client(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Seed a client and return client ID."""
    async with session_factory() as session:
        client = Client(name="Task Client", email="task@example.com")
        session.add(client)
        await session.commit()
        return client.id


@pytest.mark.asyncio
async def test_create_task(api_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Create task for existing client."""
    client_id = await _create_client(session_factory)
    response = await api_client.post(
        "/api/tasks",
        json={"client_id": client_id, "task_type": "personal_tax"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["client_id"] == client_id
    assert payload["task_type"] == "personal_tax"
    assert payload["status"] == "pending"


@pytest.mark.asyncio
async def test_create_task_with_missing_client_returns_404(api_client: AsyncClient) -> None:
    """Task creation should fail for unknown client."""
    response = await api_client.post(
        "/api/tasks",
        json={"client_id": 9999, "task_type": "personal_tax"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Client not found"


@pytest.mark.asyncio
async def test_list_tasks_with_status_filter(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """List tasks filtered by status."""
    client_id = await _create_client(session_factory)
    await api_client.post("/api/tasks", json={"client_id": client_id, "task_type": "personal_tax"})
    await api_client.post(
        "/api/tasks",
        json={
            "client_id": client_id,
            "task_type": "personal_tax",
            "assigned_agent": "personal_tax_agent",
        },
    )

    pending_response = await api_client.get("/api/tasks", params={"status": "pending"})
    assigned_response = await api_client.get("/api/tasks", params={"status": "assigned"})

    assert pending_response.status_code == 200
    assert assigned_response.status_code == 200
    assert pending_response.json()["total"] == 1
    assert assigned_response.json()["total"] == 1


@pytest.mark.asyncio
async def test_task_status_transition_flow(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Task transitions through assigned, in_progress, and completed."""
    client_id = await _create_client(session_factory)
    create_response = await api_client.post(
        "/api/tasks",
        json={"client_id": client_id, "task_type": "personal_tax"},
    )
    task_id = create_response.json()["id"]

    assign_response = await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "assigned", "assigned_agent": "personal_tax_agent"},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["status"] == "assigned"

    start_response = await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "in_progress"},
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "in_progress"

    complete_response = await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed"},
    )
    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None


@pytest.mark.asyncio
async def test_invalid_transition_returns_409(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Invalid state transition should return 409."""
    client_id = await _create_client(session_factory)
    create_response = await api_client.post(
        "/api/tasks",
        json={"client_id": client_id, "task_type": "personal_tax"},
    )
    task_id = create_response.json()["id"]

    response = await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_escalate_creates_escalation_record(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Escalation transition writes escalation row."""
    client_id = await _create_client(session_factory)
    create_response = await api_client.post(
        "/api/tasks",
        json={"client_id": client_id, "task_type": "personal_tax"},
    )
    task_id = create_response.json()["id"]

    await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "assigned", "assigned_agent": "personal_tax_agent"},
    )
    escalate_response = await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "escalated", "reason": "Missing source documentation"},
    )
    assert escalate_response.status_code == 200
    assert escalate_response.json()["status"] == "escalated"

    async with session_factory() as session:
        result = await session.execute(
            select(Escalation).where(Escalation.task_id == task_id)
        )
        escalation = result.scalars().first()
        assert escalation is not None
        assert escalation.reason == "Missing source documentation"


@pytest.mark.asyncio
async def test_retry_from_failed_to_pending(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Failed task can transition back to pending."""
    client_id = await _create_client(session_factory)
    create_response = await api_client.post(
        "/api/tasks",
        json={"client_id": client_id, "task_type": "personal_tax"},
    )
    task_id = create_response.json()["id"]

    await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "assigned", "assigned_agent": "personal_tax_agent"},
    )
    fail_response = await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "failed", "reason": "Extraction timeout"},
    )
    assert fail_response.status_code == 200
    assert fail_response.json()["status"] == "failed"

    retry_response = await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "pending"},
    )
    assert retry_response.status_code == 200
    retried = retry_response.json()
    assert retried["status"] == "pending"
    assert retried["assigned_agent"] is None
