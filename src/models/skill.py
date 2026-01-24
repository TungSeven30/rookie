"""Skill-related SQLAlchemy models for agent skills and embeddings."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class SkillFile(Base):
    """Represents a skill file containing instructions for agents.

    Skill files are versioned documents that describe how to perform
    specific tasks or handle specific scenarios.
    """

    __tablename__ = "skill_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    embeddings: Mapped[list["SkillEmbedding"]] = relationship(
        back_populates="skill_file"
    )


class SkillEmbedding(Base):
    """Represents a chunked embedding of a skill file for semantic search.

    Skill files are split into chunks and embedded for RAG queries.
    """

    __tablename__ = "skill_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_file_id: Mapped[int] = mapped_column(
        ForeignKey("skill_files.id"), nullable=False
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    skill_file: Mapped["SkillFile"] = relationship(back_populates="embeddings")
