"""Tests for Phase 5 review API endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_db
from src.main import app
from src.models.artifact import FeedbackEntry
from src.models.client import Client
from src.models.task import Escalation, Task, TaskArtifact, TaskStatus


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create async sqlite session factory for API tests."""
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
    """Create API test client with DB override."""

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


async def _create_task(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Create a test task and return its ID."""
    async with session_factory() as session:
        client = Client(name="Review Client")
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
        return task.id


@pytest.mark.asyncio
async def test_checker_run_flags_and_escalates_task(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Checker report is stored and task escalates when flags are present."""
    task_id = await _create_task(session_factory)

    response = await api_client.post(
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

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "flagged"
    assert payload["flag_count"] >= 1
    assert payload["approval_blocked"] is True
    assert payload["error_detection_rate"] == 1.0

    async with session_factory() as session:
        task = await session.get(Task, task_id)
        assert task is not None
        assert task.status == TaskStatus.ESCALATED

        escalations = await session.execute(
            select(Escalation).where(Escalation.task_id == task_id)
        )
        assert escalations.scalars().first() is not None

        artifacts = await session.execute(
            select(TaskArtifact).where(TaskArtifact.task_id == task_id)
        )
        assert any(
            artifact.artifact_type == "checker_report"
            for artifact in artifacts.scalars().all()
        )


@pytest.mark.asyncio
async def test_implicit_feedback_creates_entry_with_diff(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Implicit feedback stores original/corrected content and diff summary."""
    task_id = await _create_task(session_factory)

    response = await api_client.post(
        "/api/review/feedback/implicit",
        json={
            "task_id": task_id,
            "reviewer_id": "cpa-1",
            "original_content": "Wages: 1000\nInterest: 100",
            "corrected_content": "Wages: 1100\nInterest: 100",
            "tags": ["calculation_fix"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["feedback_type"] == "implicit"
    assert payload["reviewer_id"] == "cpa-1"
    assert payload["tags"] == ["calculation_fix"]
    assert "original" in (payload["diff_summary"] or "")

    async with session_factory() as session:
        entries = await session.execute(
            select(FeedbackEntry).where(FeedbackEntry.task_id == task_id)
        )
        entry = entries.scalars().first()
        assert entry is not None
        assert entry.feedback_type == "implicit"
        assert entry.corrected_content is not None


@pytest.mark.asyncio
async def test_explicit_feedback_and_list_endpoint(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Explicit feedback is persisted and returned by list API."""
    task_id = await _create_task(session_factory)

    create_response = await api_client.post(
        "/api/review/feedback/explicit",
        json={
            "task_id": task_id,
            "reviewer_id": "cpa-2",
            "tags": ["missing_context", "judgment_call"],
            "original_content": "Schedule C expense total: 5000",
            "corrected_content": "Schedule C expense total: 6500",
            "note": "Added missing software subscription expense.",
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["feedback_type"] == "explicit"

    list_response = await api_client.get(f"/api/review/feedback/{task_id}")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["feedback_type"] == "explicit"
    assert listed[0]["tags"] == ["missing_context", "judgment_call"]
