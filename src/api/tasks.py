"""Task management API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.models.client import Client
from src.models.task import Escalation, Task, TaskStatus
from src.orchestration.state_machine import TransitionNotAllowed, create_state_machine

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    """Payload for creating a task."""

    client_id: int = Field(gt=0)
    task_type: str = Field(min_length=1, max_length=100)
    assigned_agent: str | None = Field(default=None, max_length=100)


class TaskStatusUpdateRequest(BaseModel):
    """Payload for transitioning task status."""

    status: TaskStatus
    assigned_agent: str | None = Field(default=None, max_length=100)
    reason: str | None = None


class TaskResponse(BaseModel):
    """Task response model."""

    id: int
    client_id: int
    task_type: str
    status: str
    assigned_agent: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class TaskListResponse(BaseModel):
    """Paginated task list response."""

    items: list[TaskResponse]
    total: int
    limit: int
    offset: int


def _to_task_response(task: Task) -> TaskResponse:
    """Map SQLAlchemy task model to response model."""
    return TaskResponse(
        id=task.id,
        client_id=task.client_id,
        task_type=task.task_type,
        status=task.status.value,
        assigned_agent=task.assigned_agent,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _build_task_filters(
    client_id: int | None,
    task_type: str | None,
    assigned_agent: str | None,
    task_status: TaskStatus | None,
) -> list[object]:
    """Build SQLAlchemy filter clauses for task listing."""
    filters = []
    if client_id is not None:
        filters.append(Task.client_id == client_id)
    if task_type:
        filters.append(Task.task_type == task_type.strip())
    if assigned_agent:
        filters.append(Task.assigned_agent == assigned_agent.strip())
    if task_status is not None:
        filters.append(Task.status == task_status)
    return filters


async def _get_task_or_404(db: AsyncSession, task_id: int) -> Task:
    """Load task or raise 404."""
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Create a new task."""
    client = await db.get(Client, payload.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    task = Task(
        client_id=payload.client_id,
        task_type=payload.task_type.strip(),
        status=TaskStatus.PENDING,
        assigned_agent=None,
    )
    db.add(task)
    await db.flush()

    if payload.assigned_agent:
        sm = create_state_machine(task=task)
        sm.assign(agent=payload.assigned_agent.strip())

    await db.flush()
    return _to_task_response(task)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    client_id: int | None = Query(default=None, gt=0),
    task_type: str | None = Query(default=None, min_length=1),
    assigned_agent: str | None = Query(default=None, min_length=1),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """List tasks with optional filters and pagination."""
    filters = _build_task_filters(
        client_id=client_id,
        task_type=task_type,
        assigned_agent=assigned_agent,
        task_status=status_filter,
    )

    count_stmt = select(func.count(Task.id))
    list_stmt = select(Task).order_by(Task.created_at.desc(), Task.id.desc())
    if filters:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar() or 0)

    tasks_result = await db.execute(list_stmt.limit(limit).offset(offset))
    tasks = tasks_result.scalars().all()

    return TaskListResponse(
        items=[_to_task_response(task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Get task by ID."""
    task = await _get_task_or_404(db, task_id)
    return _to_task_response(task)


@router.patch("/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: int,
    payload: TaskStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Transition task to a new status using state-machine constraints."""
    task = await _get_task_or_404(db, task_id)
    sm = create_state_machine(task=task)

    try:
        if payload.status == TaskStatus.PENDING:
            sm.retry()
        elif payload.status == TaskStatus.ASSIGNED:
            agent = (payload.assigned_agent or "").strip()
            if not agent:
                raise HTTPException(
                    status_code=400,
                    detail="assigned_agent is required when setting status=assigned",
                )
            sm.assign(agent=agent)
        elif payload.status == TaskStatus.IN_PROGRESS:
            sm.start()
        elif payload.status == TaskStatus.COMPLETED:
            sm.complete()
        elif payload.status == TaskStatus.FAILED:
            sm.fail(reason=(payload.reason or "Task marked failed").strip())
        elif payload.status == TaskStatus.ESCALATED:
            reason = (payload.reason or "Task escalated for human review").strip()
            sm.escalate(reason=reason)
            db.add(
                Escalation(
                    task_id=task.id,
                    reason=reason,
                )
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported task status")
    except TransitionNotAllowed as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Invalid transition from {task.status.value} to {payload.status.value}"
            ),
        ) from exc

    await db.flush()
    return _to_task_response(task)
