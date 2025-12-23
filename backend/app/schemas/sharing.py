"""Document sharing schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.document import DocumentResponse


class DocumentShareBase(BaseModel):
    """Base document share schema."""

    shared_with_user_id: UUID
    permission_level: str  # read, write, admin
    expires_at: Optional[datetime] = None


class DocumentShareCreate(DocumentShareBase):
    """Schema for creating a document share."""

    pass


class DocumentShareUpdate(BaseModel):
    """Schema for updating a document share."""

    permission_level: Optional[str] = None
    expires_at: Optional[datetime] = None


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
