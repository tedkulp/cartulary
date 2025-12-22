"""Tag schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TagBase(BaseModel):
    """Base tag schema."""

    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    description: Optional[str] = None


class TagCreate(TagBase):
    """Schema for creating a tag."""

    pass


class TagUpdate(BaseModel):
    """Schema for updating a tag."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    description: Optional[str] = None


class TagResponse(TagBase):
    """Schema for tag response."""

    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentTagRequest(BaseModel):
    """Schema for adding/removing tags from a document."""

    tag_ids: list[UUID] = Field(..., description="List of tag IDs to apply")
