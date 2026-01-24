"""Task-related SQLAlchemy models."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.client import Client


class TaskStatus(enum.Enum):
    """Enumeration of possible task statuses."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class Task(Base, TimestampMixin):
    """Represents a task assigned to an agent for processing."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False
    )
    assigned_agent: Mapped[str | None] = mapped_column(String(100))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="tasks")
    escalations: Mapped[list["Escalation"]] = relationship(back_populates="task")
    artifacts: Mapped[list["TaskArtifact"]] = relationship(back_populates="task")


class Escalation(Base):
    """Represents an escalation event for a task that requires human review."""

    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    escalated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolution: Mapped[str | None] = mapped_column(Text)

    # Relationships
    task: Mapped["Task"] = relationship(back_populates="escalations")


class TaskArtifact(Base):
    """Represents an artifact produced by or related to a task."""

    __tablename__ = "task_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    task: Mapped["Task"] = relationship(back_populates="artifacts")
