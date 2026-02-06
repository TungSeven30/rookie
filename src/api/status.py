"""Status and dashboard API endpoints (Phase 5)."""

from __future__ import annotations

from datetime import datetime

import orjson
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.models.task import Escalation, Task, TaskArtifact, TaskStatus

router = APIRouter(prefix="/api/status", tags=["status"])

PROGRESS_ARTIFACT_TYPES = ("status_progress", "progress")


class TaskProgressResponse(BaseModel):
    """Task status response including latest progress snapshot."""

    task_id: int
    status: str
    assigned_agent: str | None
    progress: int
    current_stage: str
    message: str | None
    updated_at: datetime | None


class AgentStatusItem(BaseModel):
    """Aggregated status metrics for a single agent."""

    agent: str
    active_tasks: int
    assigned_tasks: int
    in_progress_tasks: int


class AttentionFlagItem(BaseModel):
    """Dashboard item requiring attention."""

    task_id: int
    reason: str
    escalated_at: datetime


class DashboardResponse(BaseModel):
    """Summary status payload for operations dashboard."""

    queue_depth: int
    completed_count: int
    failed_count: int
    escalated_count: int
    agent_activity: list[AgentStatusItem]
    attention_flags: list[AttentionFlagItem]


def _default_progress_for_status(status: TaskStatus) -> tuple[int, str, str]:
    """Map task status to fallback progress metadata."""
    if status == TaskStatus.PENDING:
        return 0, "queued", "Task queued"
    if status == TaskStatus.ASSIGNED:
        return 10, "assigned", "Task assigned to agent"
    if status == TaskStatus.IN_PROGRESS:
        return 50, "in_progress", "Task in progress"
    if status == TaskStatus.COMPLETED:
        return 100, "completed", "Task completed"
    if status == TaskStatus.FAILED:
        return 100, "failed", "Task failed"
    return 100, "escalated", "Task escalated for human review"


def _parse_artifact_payload(content: str | None) -> dict[str, object]:
    """Parse JSON payload from artifact content."""
    if not content:
        return {}
    try:
        value = orjson.loads(content)
    except orjson.JSONDecodeError:
        return {}
    if isinstance(value, dict):
        return value
    return {}


async def _fetch_task_or_404(db: AsyncSession, task_id: int) -> Task:
    """Load task or raise 404."""
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/tasks/{task_id}", response_model=TaskProgressResponse)
async def get_task_progress(
    task_id: int,
    db: AsyncSession = Depends(get_db),
) -> TaskProgressResponse:
    """Return current progress for a task (DASH-01)."""
    task = await _fetch_task_or_404(db, task_id)

    artifact_result = await db.execute(
        select(TaskArtifact)
        .where(TaskArtifact.task_id == task.id)
        .where(TaskArtifact.artifact_type.in_(PROGRESS_ARTIFACT_TYPES))
        .order_by(TaskArtifact.created_at.desc(), TaskArtifact.id.desc())
        .limit(1)
    )
    artifact = artifact_result.scalars().first()

    if artifact:
        payload = _parse_artifact_payload(artifact.content)
        progress = int(payload.get("progress", 0) or 0)
        current_stage = str(payload.get("stage", "unknown"))
        message = payload.get("message")
        message_str = str(message) if message is not None else None
        updated_at = artifact.created_at
    else:
        progress, current_stage, message_str = _default_progress_for_status(task.status)
        updated_at = task.updated_at or task.created_at

    return TaskProgressResponse(
        task_id=task.id,
        status=task.status.value,
        assigned_agent=task.assigned_agent,
        progress=progress,
        current_stage=current_stage,
        message=message_str,
        updated_at=updated_at,
    )


@router.get("/agents", response_model=list[AgentStatusItem])
async def get_agent_status(
    db: AsyncSession = Depends(get_db),
) -> list[AgentStatusItem]:
    """Return active task counts per agent (DASH-02)."""
    result = await db.execute(
        select(Task.assigned_agent, Task.status, func.count(Task.id))
        .where(Task.assigned_agent.is_not(None))
        .where(Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]))
        .group_by(Task.assigned_agent, Task.status)
    )

    grouped: dict[str, AgentStatusItem] = {}
    for assigned_agent, status, count in result.all():
        agent = str(assigned_agent)
        item = grouped.get(
            agent,
            AgentStatusItem(
                agent=agent,
                active_tasks=0,
                assigned_tasks=0,
                in_progress_tasks=0,
            ),
        )
        count_int = int(count or 0)
        item.active_tasks += count_int
        if status == TaskStatus.ASSIGNED:
            item.assigned_tasks += count_int
        elif status == TaskStatus.IN_PROGRESS:
            item.in_progress_tasks += count_int
        grouped[agent] = item

    return sorted(grouped.values(), key=lambda item: item.agent)


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_status(
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Return queue depth, completion counts, and flags (DASH-03/DASH-04)."""
    queue_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.status.in_(
                [TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
            )
        )
    )
    queue_depth = int(queue_result.scalar() or 0)

    completion_result = await db.execute(
        select(Task.status, func.count(Task.id)).group_by(Task.status)
    )
    completion_map: dict[TaskStatus, int] = {
        status: int(count or 0) for status, count in completion_result.all()
    }

    escalation_result = await db.execute(
        select(Escalation)
        .where(Escalation.resolved_at.is_(None))
        .order_by(Escalation.escalated_at.desc(), Escalation.id.desc())
        .limit(50)
    )
    unresolved = escalation_result.scalars().all()

    agent_activity = await get_agent_status(db=db)
    attention_flags = [
        AttentionFlagItem(
            task_id=entry.task_id,
            reason=entry.reason,
            escalated_at=entry.escalated_at,
        )
        for entry in unresolved
    ]

    return DashboardResponse(
        queue_depth=queue_depth,
        completed_count=completion_map.get(TaskStatus.COMPLETED, 0),
        failed_count=completion_map.get(TaskStatus.FAILED, 0),
        escalated_count=completion_map.get(TaskStatus.ESCALATED, 0),
        agent_activity=agent_activity,
        attention_flags=attention_flags,
    )

