"""External integration API endpoints (Phase 5 TaxDome hooks)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import orjson
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.core.config import settings
from src.models.client import Client
from src.models.task import Task, TaskArtifact, TaskStatus

router = APIRouter(prefix="/api/integrations/taxdome", tags=["integrations"])

ARTIFACT_TAXDOME_EVENT = "taxdome_event"
ARTIFACT_TAXDOME_STATUS = "taxdome_status_update"


class TaxDomeAssignmentPayload(BaseModel):
    """Inbound TaxDome assignment event payload."""

    external_task_id: str = Field(min_length=1)
    client_name: str = Field(min_length=1)
    client_email: str | None = None
    task_type: str = Field(min_length=1)
    assigned_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaxDomeTaskCreatedResponse(BaseModel):
    """Response after processing TaxDome assignment webhook."""

    task_id: int
    status: str
    assigned_agent: str | None
    external_task_id: str


class TaxDomeStatusUpdatePayload(BaseModel):
    """Task status update payload intended for TaxDome sync."""

    status: str = Field(pattern="^(pending|assigned|in_progress|completed|failed|escalated)$")
    note: str | None = None
    external_task_id: str | None = None
    completed_at: datetime | None = None


class TaxDomeStatusUpdateResponse(BaseModel):
    """Response for TaxDome status update endpoint."""

    task_id: int
    status: str
    synced_at: datetime
    external_task_id: str | None


def _json_dumps(payload: dict[str, Any]) -> str:
    """Serialize dict payload to JSON string."""
    return orjson.dumps(payload).decode("utf-8")


def _parse_task_status(raw: str) -> TaskStatus:
    """Convert lowercase API status string into TaskStatus enum."""
    return TaskStatus(raw)


def _verify_taxdome_webhook_token(x_taxdome_token: str | None) -> None:
    """Validate webhook token when configured."""
    expected = settings.taxdome_webhook_secret
    if not expected:
        return
    if x_taxdome_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TaxDome webhook token",
        )


async def _resolve_client(
    db: AsyncSession,
    client_name: str,
    client_email: str | None,
) -> Client:
    """Find existing client by email/name or create new one."""
    if client_email:
        result = await db.execute(
            select(Client).where(Client.email == client_email).limit(1)
        )
        by_email = result.scalars().first()
        if by_email is not None:
            return by_email

    result = await db.execute(select(Client).where(Client.name == client_name).limit(1))
    by_name = result.scalars().first()
    if by_name is not None:
        if client_email and not by_name.email:
            by_name.email = client_email
        return by_name

    client = Client(name=client_name, email=client_email)
    db.add(client)
    await db.flush()
    return client


async def _get_task_or_404(db: AsyncSession, task_id: int) -> Task:
    """Load task or raise HTTP 404."""
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post(
    "/webhook/task-assigned",
    response_model=TaxDomeTaskCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def handle_taxdome_task_assigned(
    payload: TaxDomeAssignmentPayload,
    db: AsyncSession = Depends(get_db),
    x_taxdome_token: str | None = Header(default=None, alias="X-TaxDome-Token"),
) -> TaxDomeTaskCreatedResponse:
    """Process TaxDome task assignment webhook (INT-01)."""
    _verify_taxdome_webhook_token(x_taxdome_token)

    client = await _resolve_client(
        db=db,
        client_name=payload.client_name,
        client_email=payload.client_email,
    )

    task = Task(
        client_id=client.id,
        task_type=payload.task_type,
        status=TaskStatus.ASSIGNED,
        assigned_agent=payload.assigned_agent or "personal_tax_agent",
    )
    db.add(task)
    await db.flush()

    db.add(
        TaskArtifact(
            task_id=task.id,
            artifact_type=ARTIFACT_TAXDOME_EVENT,
            content=_json_dumps(
                {
                    "event": "task_assigned",
                    "external_task_id": payload.external_task_id,
                    "client_name": payload.client_name,
                    "client_email": payload.client_email,
                    "task_type": payload.task_type,
                    "assigned_agent": task.assigned_agent,
                    "metadata": payload.metadata,
                }
            ),
        )
    )

    return TaxDomeTaskCreatedResponse(
        task_id=task.id,
        status=task.status.value,
        assigned_agent=task.assigned_agent,
        external_task_id=payload.external_task_id,
    )


@router.post(
    "/tasks/{task_id}/status",
    response_model=TaxDomeStatusUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def update_taxdome_task_status(
    task_id: int,
    payload: TaxDomeStatusUpdatePayload,
    db: AsyncSession = Depends(get_db),
    x_taxdome_token: str | None = Header(default=None, alias="X-TaxDome-Token"),
) -> TaxDomeStatusUpdateResponse:
    """Handle TaxDome status update callback/sync request (INT-02)."""
    _verify_taxdome_webhook_token(x_taxdome_token)
    task = await _get_task_or_404(db, task_id)

    task.status = _parse_task_status(payload.status)
    if task.status == TaskStatus.COMPLETED:
        task.completed_at = payload.completed_at or datetime.utcnow()

    synced_at = datetime.utcnow()
    db.add(
        TaskArtifact(
            task_id=task.id,
            artifact_type=ARTIFACT_TAXDOME_STATUS,
            content=_json_dumps(
                {
                    "external_task_id": payload.external_task_id,
                    "status": payload.status,
                    "note": payload.note,
                    "completed_at": (
                        task.completed_at.isoformat() if task.completed_at else None
                    ),
                    "synced_at": synced_at.isoformat(),
                }
            ),
        )
    )

    return TaxDomeStatusUpdateResponse(
        task_id=task.id,
        status=task.status.value,
        synced_at=synced_at,
        external_task_id=payload.external_task_id,
    )

