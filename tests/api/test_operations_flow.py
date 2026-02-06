"""End-to-end API flow tests for the operations workspace."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db
from src.main import app
from src.models.artifact import FeedbackEntry
from src.models.client import Client
from src.models.task import Escalation, Task, TaskArtifact


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create sqlite-backed session factory for operations flow tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Client.__table__.create)
        await conn.run_sync(Task.__table__.create)
        await conn.run_sync(TaskArtifact.__table__.create)
        await conn.run_sync(Escalation.__table__.create)
        await conn.run_sync(FeedbackEntry.__table__.create)

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
async def test_operations_workspace_api_flow(api_client: AsyncClient) -> None:
    """Cover the dashboard/checker/feedback flow used by operations UI."""
    create_client_response = await api_client.post(
        "/api/clients",
        json={"name": "Flow Client", "email": "flow@example.com"},
    )
    assert create_client_response.status_code == 201
    client_id = create_client_response.json()["id"]

    create_task_response = await api_client.post(
        "/api/tasks",
        json={
            "client_id": client_id,
            "task_type": "personal_tax",
            "assigned_agent": "personal_tax_agent",
        },
    )
    assert create_task_response.status_code == 201
    task_id = create_task_response.json()["id"]
    assert create_task_response.json()["status"] == "assigned"

    dashboard_before = await api_client.get("/api/status/dashboard")
    assert dashboard_before.status_code == 200
    assert dashboard_before.json()["queue_depth"] >= 1

    start_response = await api_client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "in_progress"},
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "in_progress"

    checker_response = await api_client.post(
        "/api/review/checker/run",
        json={
            "task_id": task_id,
            "source_values": {"wages": 1000, "interest": 100},
            "prepared_values": {"wages": 1300, "interest": 100},
            "prior_year_values": {"wages": 1000},
            "documented_reasons": {},
            "injected_error_fields": ["wages"],
        },
    )
    assert checker_response.status_code == 200
    assert checker_response.json()["flag_count"] >= 1
    assert checker_response.json()["approval_blocked"] is True

    implicit_feedback_response = await api_client.post(
        "/api/review/feedback/implicit",
        json={
            "task_id": task_id,
            "reviewer_id": "cpa-flow",
            "original_content": "Wages: 1300",
            "corrected_content": "Wages: 1000",
            "tags": ["calculation_fix"],
        },
    )
    assert implicit_feedback_response.status_code == 201
    assert implicit_feedback_response.json()["feedback_type"] == "implicit"
    assert implicit_feedback_response.json()["diff_summary"] is not None

    explicit_feedback_response = await api_client.post(
        "/api/review/feedback/explicit",
        json={
            "task_id": task_id,
            "reviewer_id": "cpa-flow",
            "tags": ["missing_context"],
            "original_content": "No reason documented",
            "corrected_content": "Variance explained by bonus correction",
            "note": "Client confirmed corrected W-2 was uploaded.",
        },
    )
    assert explicit_feedback_response.status_code == 201
    assert explicit_feedback_response.json()["feedback_type"] == "explicit"

    feedback_history = await api_client.get(f"/api/review/feedback/{task_id}")
    assert feedback_history.status_code == 200
    assert len(feedback_history.json()) == 2

    dashboard_after = await api_client.get("/api/status/dashboard")
    assert dashboard_after.status_code == 200
    assert dashboard_after.json()["escalated_count"] >= 1
    assert any(
        flag["task_id"] == task_id for flag in dashboard_after.json()["attention_flags"]
    )
