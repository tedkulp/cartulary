"""Document sharing schemas."""
from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import UUID

from pydantic import AfterValidator, BaseModel

from app.schemas.document import DocumentResponse


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """
    Read a naive expiry as UTC.

    `document_shares.expires_at` is `timestamptz`: it stores an instant, so a
    timestamp arriving without an offset has to be given one. UTC is what every
    writer already meant, and saying it here — at the edge — means nothing
    further in ever handles a timestamp whose zone is a guess. See ADR 0008.
    """
    if value is None or value.tzinfo is not None:
        return value

    return value.replace(tzinfo=timezone.utc)


# An instant. Sent with an offset, or without one and read as UTC.
ExpiresAt = Annotated[Optional[datetime], AfterValidator(_as_utc)]


class DocumentShareBase(BaseModel):
    """Base document share schema."""

    shared_with_user_id: UUID
    permission_level: str  # read, write, admin
    expires_at: ExpiresAt = None


class DocumentShareCreate(DocumentShareBase):
    """Schema for creating a document share."""

    pass


class DocumentShareUpdate(BaseModel):
    """Schema for updating a document share."""

    permission_level: Optional[str] = None
    expires_at: ExpiresAt = None


class DocumentShareResponse(DocumentShareBase):
    """Schema for document share response."""

    id: UUID
    document_id: UUID
    shared_by_user_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


class SharedDocumentResponse(BaseModel):
    """Schema for a shared document (combines document and share info)."""

    document: DocumentResponse
    share: DocumentShareResponse

    class Config:
        from_attributes = True
