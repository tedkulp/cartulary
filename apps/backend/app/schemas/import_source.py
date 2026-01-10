"""Import source schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.import_source import ImportSourceType, ImportSourceStatus


class ImportSourceBase(BaseModel):
    """Base import source schema."""

    name: str = Field(..., min_length=1, max_length=255)
    source_type: ImportSourceType
    status: ImportSourceStatus = ImportSourceStatus.ACTIVE


class ImportSourceCreate(ImportSourceBase):
    """Schema for creating an import source."""

    # Directory-specific fields
    watch_path: Optional[str] = None
    move_after_import: bool = False
    move_to_path: Optional[str] = None
    delete_after_import: bool = False

    # IMAP-specific fields
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None
    imap_use_ssl: bool = True
    imap_mailbox: str = "INBOX"
    imap_processed_folder: Optional[str] = None


class ImportSourceUpdate(BaseModel):
    """Schema for updating an import source."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[ImportSourceStatus] = None

    # Directory-specific fields
    watch_path: Optional[str] = None
    move_after_import: Optional[bool] = None
    move_to_path: Optional[str] = None
    delete_after_import: Optional[bool] = None

    # IMAP-specific fields
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None
    imap_use_ssl: Optional[bool] = None
    imap_mailbox: Optional[str] = None
    imap_processed_folder: Optional[str] = None


class ImportSourceResponse(ImportSourceBase):
    """Schema for import source response."""

    id: UUID
    owner_id: UUID

    # Directory-specific fields
    watch_path: Optional[str] = None
    move_after_import: bool
    move_to_path: Optional[str] = None
    delete_after_import: bool

    # IMAP-specific fields (password excluded for security)
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_use_ssl: bool
    imap_mailbox: Optional[str] = None
    imap_processed_folder: Optional[str] = None

    last_run: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
