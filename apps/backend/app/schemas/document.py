"""Document schemas."""
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, field_serializer

if TYPE_CHECKING:
    from app.schemas.tag import TagResponse


class DocumentBase(BaseModel):
    """Base document schema."""

    title: str = Field(..., min_length=1, max_length=500)


class DocumentCreate(DocumentBase):
    """Schema for creating a document."""

    pass


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    is_public: Optional[bool] = None


class DocumentResponse(DocumentBase):
    """Schema for document response."""

    id: UUID
    description: Optional[str] = None
    original_filename: str
    file_size: int
    mime_type: str
    checksum: str
    processing_status: str
    ocr_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    uploaded_by: Optional[UUID] = None
    tags: List["TagResponse"] = []

    # LLM-extracted metadata
    extracted_title: Optional[str] = None
    extracted_date: Optional[date] = None  # Date only (no time)
    extracted_correspondent: Optional[str] = None
    extracted_document_type: Optional[str] = None
    extracted_summary: Optional[str] = None

    @computed_field
    @property
    def file_extension(self) -> str:
        """Extract file extension from mime type (actual stored file type)."""
        # Map common MIME types to extensions
        mime_to_ext = {
            "application/pdf": "pdf",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/tiff": "tiff",
            "image/tif": "tif",
            "image/bmp": "bmp",
            "image/gif": "gif",
        }
        
        # Try to get from mime_type first (reflects actual stored file)
        if self.mime_type and self.mime_type.lower() in mime_to_ext:
            return mime_to_ext[self.mime_type.lower()]
        
        # Fallback to original filename extension
        if "." in self.original_filename:
            return self.original_filename.rsplit(".", 1)[-1].lower()
        
        return ""

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to ISO 8601 format string with UTC timezone."""
        if not value:
            return None
        # If naive datetime, assume it's UTC and make it timezone-aware
        if value.tzinfo is None:
            from datetime import timezone
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    
    @field_serializer('extracted_date')
    def serialize_date(self, value: Optional[date]) -> Optional[str]:
        """Serialize date to YYYY-MM-DD format (no time/timezone)."""
        if not value:
            return None
        return value.isoformat()  # Returns YYYY-MM-DD format

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for paginated document list."""

    documents: list[DocumentResponse]
    total: int
    skip: int
    limit: int


# Import TagResponse and update forward references
from app.schemas.tag import TagResponse

DocumentResponse.model_rebuild()
