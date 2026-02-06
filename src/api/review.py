"""Review Infrastructure API endpoints (Phase 5)."""

from __future__ import annotations

from datetime import datetime
import difflib

import orjson
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.checker import CheckerAgent
from src.api.deps import get_db
from src.models.artifact import FeedbackEntry
from src.models.task import Escalation, Task, TaskArtifact, TaskStatus

router = APIRouter(prefix="/api/review", tags=["review"])

checker_agent = CheckerAgent()

ARTIFACT_CHECKER_REPORT = "checker_report"
ARTIFACT_FEEDBACK_IMPLICIT = "feedback_implicit"
ARTIFACT_FEEDBACK_EXPLICIT = "feedback_explicit"


class CheckerRunRequest(BaseModel):
    """Request payload for checker execution."""

    task_id: int = Field(gt=0)
    source_values: dict[str, str | int | float]
    prepared_values: dict[str, str | int | float]
    prior_year_values: dict[str, str | int | float] = Field(default_factory=dict)
    documented_reasons: dict[str, str] = Field(default_factory=dict)
    injected_error_fields: list[str] = Field(default_factory=list)


class CheckerFlagResponse(BaseModel):
    """Checker finding returned to callers."""

    code: str
    field: str
    severity: str
    message: str
    source_value: str | None = None
    prepared_value: str | None = None
    prior_year_value: str | None = None
    variance_pct: float | None = None


class CheckerReportResponse(BaseModel):
    """Checker report API response model."""

    task_id: int
    status: str
    flag_count: int
    flags: list[CheckerFlagResponse]
    approval_blocked: bool
    error_detection_rate: float | None = None


class ImplicitFeedbackRequest(BaseModel):
    """Payload for implicit feedback capture (diff-based)."""

    task_id: int = Field(gt=0)
    reviewer_id: str | None = None
    original_content: str = Field(min_length=1)
    corrected_content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class ExplicitFeedbackRequest(BaseModel):
    """Payload for explicit feedback capture (tag-based)."""

    task_id: int = Field(gt=0)
    reviewer_id: str | None = None
    tags: list[str] = Field(min_length=1)
    original_content: str = Field(min_length=1)
    corrected_content: str | None = None
    note: str | None = None


class FeedbackResponse(BaseModel):
    """Feedback entry response model."""

    id: int
    task_id: int
    reviewer_id: str | None
    feedback_type: str
    tags: list[str]
    diff_summary: str | None
    created_at: datetime


def _json_dumps(payload: dict[str, object]) -> str:
    """Serialize JSON payload."""
    return orjson.dumps(payload).decode("utf-8")


def _build_diff_summary(original_content: str, corrected_content: str) -> str:
    """Build concise unified diff summary."""
    diff_lines = list(
        difflib.unified_diff(
            original_content.splitlines(),
            corrected_content.splitlines(),
            fromfile="original",
            tofile="corrected",
            lineterm="",
        )
    )
    if not diff_lines:
        return "No textual diff detected."

    max_lines = 20
    clipped = diff_lines[:max_lines]
    if len(diff_lines) > max_lines:
        clipped.append("... (diff truncated)")
    return "\n".join(clipped)


async def _get_task_or_404(session: AsyncSession, task_id: int) -> Task:
    """Fetch task or raise HTTP 404."""
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post(
    "/checker/run",
    response_model=CheckerReportResponse,
    status_code=status.HTTP_200_OK,
)
async def run_checker(
    request: CheckerRunRequest,
    db: AsyncSession = Depends(get_db),
) -> CheckerReportResponse:
    """Run checker analysis and persist report as task artifact."""
    task = await _get_task_or_404(db, request.task_id)

    report = checker_agent.run_check(
        task_id=request.task_id,
        source_values=request.source_values,
        prepared_values=request.prepared_values,
        prior_year_values=request.prior_year_values,
        documented_reasons=request.documented_reasons,
        injected_error_fields=request.injected_error_fields,
    )
    report_data = report.to_dict()

    db.add(
        TaskArtifact(
            task_id=task.id,
            artifact_type=ARTIFACT_CHECKER_REPORT,
            content=_json_dumps(report_data),
        )
    )

    if report.flag_count > 0:
        db.add(
            Escalation(
                task_id=task.id,
                reason=f"Checker flagged {report.flag_count} issue(s) for review.",
            )
        )
        if task.status in {
            TaskStatus.PENDING,
            TaskStatus.ASSIGNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
        }:
            task.status = TaskStatus.ESCALATED

    return CheckerReportResponse(**report_data)


@router.post(
    "/feedback/implicit",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_implicit_feedback(
    request: ImplicitFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Capture implicit feedback via diff between original and corrected content."""
    task = await _get_task_or_404(db, request.task_id)
    _ = task

    diff_summary = _build_diff_summary(request.original_content, request.corrected_content)
    entry = FeedbackEntry(
        task_id=request.task_id,
        reviewer_id=request.reviewer_id,
        feedback_type="implicit",
        original_content=request.original_content,
        corrected_content=request.corrected_content,
        diff_summary=diff_summary,
        tags=request.tags or None,
    )
    db.add(entry)
    await db.flush()

    db.add(
        TaskArtifact(
            task_id=request.task_id,
            artifact_type=ARTIFACT_FEEDBACK_IMPLICIT,
            content=_json_dumps(
                {
                    "feedback_entry_id": entry.id,
                    "reviewer_id": request.reviewer_id,
                    "tag_count": len(request.tags),
                }
            ),
        )
    )

    return FeedbackResponse(
        id=entry.id,
        task_id=entry.task_id,
        reviewer_id=entry.reviewer_id,
        feedback_type=entry.feedback_type,
        tags=entry.tags or [],
        diff_summary=entry.diff_summary,
        created_at=entry.created_at,
    )


@router.post(
    "/feedback/explicit",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_explicit_feedback(
    request: ExplicitFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Capture explicit reviewer feedback with tags and optional correction text."""
    task = await _get_task_or_404(db, request.task_id)
    _ = task

    corrected_content = request.corrected_content
    diff_summary = None
    if corrected_content:
        diff_summary = _build_diff_summary(request.original_content, corrected_content)
    if request.note:
        diff_summary = (
            f"{request.note}\n\n{diff_summary}" if diff_summary else request.note
        )

    entry = FeedbackEntry(
        task_id=request.task_id,
        reviewer_id=request.reviewer_id,
        feedback_type="explicit",
        original_content=request.original_content,
        corrected_content=corrected_content,
        diff_summary=diff_summary,
        tags=request.tags,
    )
    db.add(entry)
    await db.flush()

    db.add(
        TaskArtifact(
            task_id=request.task_id,
            artifact_type=ARTIFACT_FEEDBACK_EXPLICIT,
            content=_json_dumps(
                {
                    "feedback_entry_id": entry.id,
                    "reviewer_id": request.reviewer_id,
                    "tags": request.tags,
                }
            ),
        )
    )

    return FeedbackResponse(
        id=entry.id,
        task_id=entry.task_id,
        reviewer_id=entry.reviewer_id,
        feedback_type=entry.feedback_type,
        tags=entry.tags or [],
        diff_summary=entry.diff_summary,
        created_at=entry.created_at,
    )


@router.get(
    "/feedback/{task_id}",
    response_model=list[FeedbackResponse],
    status_code=status.HTTP_200_OK,
)
async def list_feedback_for_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[FeedbackResponse]:
    """List all feedback entries attached to a task."""
    await _get_task_or_404(db, task_id)

    result = await db.execute(
        select(FeedbackEntry)
        .where(FeedbackEntry.task_id == task_id)
        .order_by(FeedbackEntry.created_at.desc(), FeedbackEntry.id.desc())
    )
    entries = result.scalars().all()
    return [
        FeedbackResponse(
            id=entry.id,
            task_id=entry.task_id,
            reviewer_id=entry.reviewer_id,
            feedback_type=entry.feedback_type,
            tags=entry.tags or [],
            diff_summary=entry.diff_summary,
            created_at=entry.created_at,
        )
        for entry in entries
    ]

