"""Import source models."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, Text, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ImportSourceType(str, enum.Enum):
    """Import source type enum."""
    DIRECTORY = "directory"
    IMAP = "imap"


class ImportSourceStatus(str, enum.Enum):
    """Import source status enum."""
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class ImportSource(Base):
    """Import source model."""

    __tablename__ = "import_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[ImportSourceType] = mapped_column(
        SQLEnum(ImportSourceType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    status: Mapped[ImportSourceStatus] = mapped_column(
        SQLEnum(ImportSourceStatus, values_callable=lambda x: [e.value for e in x]),
        default=ImportSourceStatus.ACTIVE,
        nullable=False
    )

    # Directory-specific fields
    watch_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    move_after_import: Mapped[bool] = mapped_column(Boolean, default=False)
    move_to_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    delete_after_import: Mapped[bool] = mapped_column(Boolean, default=False)

    # IMAP-specific fields
    imap_server: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_port: Mapped[int | None] = mapped_column(nullable=True)
    imap_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    imap_mailbox: Mapped[str | None] = mapped_column(String(255), default="INBOX")
    imap_processed_folder: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Common fields
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
