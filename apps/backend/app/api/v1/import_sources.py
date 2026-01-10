"""Import source API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.permissions import SystemPermissions, require_permission
from app.models.user import User
from app.models.import_source import ImportSource
from app.schemas.import_source import (
    ImportSourceCreate,
    ImportSourceUpdate,
    ImportSourceResponse
)

router = APIRouter(prefix="/import-sources", tags=["import-sources"])


@router.get("", response_model=List[ImportSourceResponse])
async def list_import_sources(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_permission(SystemPermissions.DOCUMENTS_READ)),
    db: Session = Depends(get_db)
):
    """List all import sources for the current user."""
    sources = db.query(ImportSource).filter(
        ImportSource.owner_id == current_user.id
    ).offset(skip).limit(limit).all()
    return sources


@router.post("", response_model=ImportSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_import_source(
    source_data: ImportSourceCreate,
    current_user: User = Depends(require_permission(SystemPermissions.DOCUMENTS_WRITE)),
    db: Session = Depends(get_db)
):
    """Create a new import source."""
    # Create new import source
    import_source = ImportSource(
        name=source_data.name,
        source_type=source_data.source_type,
        status=source_data.status,
        owner_id=current_user.id,
        # Directory fields
        watch_path=source_data.watch_path,
        move_after_import=source_data.move_after_import,
        move_to_path=source_data.move_to_path,
        delete_after_import=source_data.delete_after_import,
        # IMAP fields
        imap_server=source_data.imap_server,
        imap_port=source_data.imap_port,
        imap_username=source_data.imap_username,
        imap_password=source_data.imap_password,
        imap_use_ssl=source_data.imap_use_ssl,
        imap_mailbox=source_data.imap_mailbox,
        imap_processed_folder=source_data.imap_processed_folder,
    )

    db.add(import_source)
    db.commit()
    db.refresh(import_source)

    return import_source


@router.get("/{source_id}", response_model=ImportSourceResponse)
async def get_import_source(
    source_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.DOCUMENTS_READ)),
    db: Session = Depends(get_db)
):
    """Get a specific import source by ID."""
    source = db.query(ImportSource).filter(
        ImportSource.id == source_id,
        ImportSource.owner_id == current_user.id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import source not found"
        )

    return source


@router.patch("/{source_id}", response_model=ImportSourceResponse)
async def update_import_source(
    source_id: UUID,
    source_data: ImportSourceUpdate,
    current_user: User = Depends(require_permission(SystemPermissions.DOCUMENTS_WRITE)),
    db: Session = Depends(get_db)
):
    """Update an import source."""
    source = db.query(ImportSource).filter(
        ImportSource.id == source_id,
        ImportSource.owner_id == current_user.id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import source not found"
        )

    # Update fields if provided
    update_data = source_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    db.commit()
    db.refresh(source)

    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_import_source(
    source_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.DOCUMENTS_WRITE)),
    db: Session = Depends(get_db)
):
    """Delete an import source."""
    source = db.query(ImportSource).filter(
        ImportSource.id == source_id,
        ImportSource.owner_id == current_user.id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import source not found"
        )

    db.delete(source)
    db.commit()

    return None
