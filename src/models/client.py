"""Client-related SQLAlchemy models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.task import Task


class Client(Base, TimestampMixin):
    """Represents a client (taxpayer) in the system."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(back_populates="client")
    profile_entries: Mapped[list["ClientProfileEntry"]] = relationship(
        back_populates="client"
    )


class ClientProfileEntry(Base):
    """Represents an append-only profile entry for a client.

    Uses append-only log pattern for full history and conflict-free updates.
    """

    __tablename__ = "client_profile_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="profile_entries")
