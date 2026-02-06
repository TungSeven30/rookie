"""Tests for Phase 5 status and dashboard endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import orjson
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db
from src.main import app
from src.models.client import Client
from src.models.task import Escalation, Task, TaskArtifact, TaskStatus


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create async sqlite session factory for status API tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Client.__table__.create)
        await conn.run_sync(Task.__table__.create)
        await conn.run_sync(TaskArtifact.__table__.create)
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
    """Create API client with database override."""

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


async def _seed_status_data(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Seed tasks/artifacts/escalations and return one task id."""
    async with session_factory() as session:
        client = Client(name="Status Client")
        session.add(client)
        await session.flush()

        t1 = Task(
            client_id=client.id,
            task_type="personal_tax",
            status=TaskStatus.IN_PROGRESS,
            assigned_agent="personal_tax_agent",
        )
        t2 = Task(
            client_id=client.id,
            task_type="business_tax",
            status=TaskStatus.ASSIGNED,
            assigned_agent="business_tax_agent",
        )
        t3 = Task(
            client_id=client.id,
            task_type="bookkeeping",
            status=TaskStatus.COMPLETED,
            assigned_agent="bookkeeping_agent",
        )
        t4 = Task(
            client_id=client.id,
            task_type="personal_tax",
            status=TaskStatus.ESCALATED,
            assigned_agent="checker_agent",
        )
        session.add_all([t1, t2, t3, t4])
        await session.flush()

        session.add(
            TaskArtifact(
                task_id=t1.id,
                artifact_type="status_progress",
                content=orjson.dumps(
                    {
                        "stage": "extracting",
                        "progress": 45,
                        "message": "Extracting values from W-2",
                    }
                ).decode("utf-8"),
            )
        )
        session.add(
            Escalation(
                task_id=t4.id,
                reason="Missing source documentation for Schedule E variance.",
            )
        )
        await session.commit()
        return t1.id


@pytest.mark.asyncio
async def test_get_task_progress_uses_latest_progress_artifact(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Task progress endpoint should surface stored progress event details."""
    task_id = await _seed_status_data(session_factory)

    response = await api_client.get(f"/api/status/tasks/{task_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task_id
    assert payload["status"] == "in_progress"
    assert payload["progress"] == 45
    assert payload["current_stage"] == "extracting"
    assert "W-2" in (payload["message"] or "")


@pytest.mark.asyncio
async def test_get_agent_status_returns_active_task_counts(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Agent status endpoint should aggregate assigned/in-progress tasks."""
    await _seed_status_data(session_factory)
    response = await api_client.get("/api/status/agents")

    assert response.status_code == 200
    payload = response.json()
    by_agent = {item["agent"]: item for item in payload}

    assert by_agent["personal_tax_agent"]["in_progress_tasks"] == 1
    assert by_agent["personal_tax_agent"]["active_tasks"] == 1
    assert by_agent["business_tax_agent"]["assigned_tasks"] == 1
    assert by_agent["business_tax_agent"]["active_tasks"] == 1


@pytest.mark.asyncio
async def test_dashboard_returns_queue_and_attention_flags(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dashboard endpoint should include queue depth and unresolved flags."""
    await _seed_status_data(session_factory)
    response = await api_client.get("/api/status/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["queue_depth"] == 2
    assert payload["completed_count"] == 1
    assert payload["escalated_count"] == 1
    assert len(payload["attention_flags"]) == 1
    assert "Missing source documentation" in payload["attention_flags"][0]["reason"]
