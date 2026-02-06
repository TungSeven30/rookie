"""Artifact-related SQLAlchemy models for feedback and embeddings."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class FeedbackEntry(Base):
    """Represents human reviewer feedback on AI-generated output.

    Used for learning from corrections and improving future outputs.
    """

    __tablename__ = "feedback_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(100))
    feedback_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_content: Mapped[str | None] = mapped_column(Text)
    diff_summary: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)).with_variant(JSON, "sqlite")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class DocumentEmbedding(Base):
    """Represents a document embedding for semantic search.

    Used for RAG (Retrieval Augmented Generation) queries.
    """

    __tablename__ = "document_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
