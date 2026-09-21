"""The durable record of an attachment an import source can never take in."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.import_source import ImportSource


#: One record per (source, message, attachment bytes). Naming the index lets a
#: conflicting insert be recognised as "already recorded" rather than a fault.
IMPORT_FAILURE_ATTACHMENT_INDEX = "ux_import_failures_source_message_checksum"

#: Message-Ids are bounded by RFC 5322's line length; longer ones are truncated
#: to fit, which cannot make two different messages collide in practice.
MESSAGE_KEY_LENGTH = 512


class ImportFailure(Base):
    """An attachment this import source will never accept, and why.

    A Document that failed to be created is not a Document, so there is nowhere
    else to write this down. The row is what lets the message carrying the
    attachment be completed without the failure being silently discarded, and
    what stops the next pass attempting the same bytes again. See ADR 0011.
    """

    __tablename__ = "import_failures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    import_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The identity of the message the attachment arrived on: its Message-Id
    # where it has one, otherwise the mailbox's UIDVALIDITY and the message's
    # UID. Stable across reconnects, and across a move to another folder.
    message_key: Mapped[str] = mapped_column(String(MESSAGE_KEY_LENGTH), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 of the attachment bytes: the same identity intake deduplicates by.
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    # A moment in time, so timestamptz: this table is new and has no naive
    # history to keep company with. See ADR 0008.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    import_source: Mapped["ImportSource"] = relationship(
        "ImportSource", lazy="selectin"
    )

    __table_args__ = (
        Index(
            IMPORT_FAILURE_ATTACHMENT_INDEX,
            "import_source_id",
            "message_key",
            "checksum",
            unique=True,
        ),
    )
