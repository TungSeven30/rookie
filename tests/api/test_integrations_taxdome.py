"""Tests for TaxDome integration endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db
from src.core.config import settings
from src.main import app
from src.models.client import Client
from src.models.task import Task, TaskArtifact, TaskStatus


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create sqlite-backed session factory for TaxDome API tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Client.__table__.create)
        await conn.run_sync(Task.__table__.create)
        await conn.run_sync(TaskArtifact.__table__.create)

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
async def test_taxdome_assignment_webhook_creates_task_and_artifact(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TaxDome webhook should create an assigned task for the client."""
    monkeypatch.setattr(settings, "taxdome_webhook_secret", "secret-1")

    response = await api_client.post(
        "/api/integrations/taxdome/webhook/task-assigned",
        headers={"X-TaxDome-Token": "secret-1"},
        json={
            "external_task_id": "td-123",
            "client_name": "TaxDome Client",
            "client_email": "client@example.com",
            "task_type": "personal_tax",
            "assigned_agent": "personal_tax_agent",
            "metadata": {"priority": "high"},
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "assigned"
    assert payload["external_task_id"] == "td-123"

    async with session_factory() as session:
        task = await session.get(Task, payload["task_id"])
        assert task is not None
        assert task.status == TaskStatus.ASSIGNED

        artifacts = await session.execute(
            select(TaskArtifact).where(TaskArtifact.task_id == task.id)
        )
        assert any(
            item.artifact_type == "taxdome_event" for item in artifacts.scalars().all()
        )


@pytest.mark.asyncio
async def test_taxdome_status_update_changes_task_status(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TaxDome status endpoint updates task status and writes sync artifact."""
    monkeypatch.setattr(settings, "taxdome_webhook_secret", None)

    async with session_factory() as session:
        client = Client(name="Status Client")
        session.add(client)
        await session.flush()
        task = Task(
            client_id=client.id,
            task_type="personal_tax",
            status=TaskStatus.IN_PROGRESS,
            assigned_agent="personal_tax_agent",
        )
        session.add(task)
        await session.commit()
        task_id = task.id

    response = await api_client.post(
        f"/api/integrations/taxdome/tasks/{task_id}/status",
        json={
            "status": "completed",
            "note": "Marked complete in TaxDome",
            "external_task_id": "td-456",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task_id
    assert payload["status"] == "completed"
    assert payload["external_task_id"] == "td-456"

    async with session_factory() as session:
        task = await session.get(Task, task_id)
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None


@pytest.mark.asyncio
async def test_taxdome_webhook_rejects_invalid_token(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Webhook should return 401 when token does not match configured secret."""
    monkeypatch.setattr(settings, "taxdome_webhook_secret", "expected-secret")

    response = await api_client.post(
        "/api/integrations/taxdome/webhook/task-assigned",
        headers={"X-TaxDome-Token": "wrong-secret"},
        json={
            "external_task_id": "td-999",
            "client_name": "Bad Token Client",
            "task_type": "personal_tax",
        },
    )
    assert response.status_code == 401
