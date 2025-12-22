"""Document schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class DocumentBase(BaseModel):
    """Base document schema."""

    title: str = Field(..., min_length=1, max_length=500)


class DocumentCreate(DocumentBase):
    """Schema for creating a document."""

    pass


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)


class DocumentResponse(DocumentBase):
    """Schema for document response."""

    id: UUID
    original_filename: str
    file_size: int
    mime_type: str
    checksum: str
    processing_status: str
    ocr_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # LLM-extracted metadata
    extracted_title: Optional[str] = None
    extracted_date: Optional[datetime] = None
    extracted_sender: Optional[str] = None
    extracted_recipient: Optional[str] = None

    @computed_field
    @property
    def file_extension(self) -> str:
        """Extract file extension from original filename."""
        if "." in self.original_filename:
            return self.original_filename.rsplit(".", 1)[-1].lower()
        return ""

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for paginated document list."""

    documents: list[DocumentResponse]
    total: int
    skip: int
    limit: int
