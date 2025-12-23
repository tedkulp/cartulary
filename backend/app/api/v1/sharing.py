"""Document sharing API endpoints."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import (
    PermissionLevel,
    get_permission_service,
    PermissionService,
    require_document_access
)
from app.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.models.sharing import DocumentShare
from app.schemas.sharing import (
    DocumentShareResponse,
    DocumentShareCreate,
    DocumentShareUpdate,
    SharedDocumentResponse
)

router = APIRouter()


@router.get("/documents/{document_id}/shares", response_model=List[DocumentShareResponse])
async def list_document_shares(
    document_id: UUID,
    document: Document = Depends(require_document_access(PermissionLevel.ADMIN)),
    db: Session = Depends(get_db)
):
    """
    List all shares for a document.

    Requires admin access to the document.
    """
    shares = (
        db.query(DocumentShare)
        .filter(DocumentShare.document_id == document_id)
        .all()
    )
    return shares


@router.post(
    "/documents/{document_id}/shares",
    response_model=DocumentShareResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_document_share(
    document_id: UUID,
    share_data: DocumentShareCreate,
    document: Document = Depends(require_document_access(PermissionLevel.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Share a document with another user.

    Requires admin access to the document.
    """
    # Verify shared_with user exists
    shared_with_user = db.query(User).filter(User.id == share_data.shared_with_user_id).first()
    if not shared_with_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User to share with not found"
        )

    # Check if share already exists
    existing_share = (
        db.query(DocumentShare)
        .filter(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == share_data.shared_with_user_id
        )
        .first()
    )

    if existing_share:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document is already shared with this user"
        )

    # Validate permission level
    if share_data.permission_level not in [
        PermissionLevel.READ,
        PermissionLevel.WRITE,
        PermissionLevel.ADMIN
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid permission level. Must be 'read', 'write', or 'admin'"
        )

    # Create share
    db_share = DocumentShare(
        document_id=document_id,
        shared_with_user_id=share_data.shared_with_user_id,
        shared_by_user_id=current_user.id,
        permission_level=share_data.permission_level,
        expires_at=share_data.expires_at
    )

    db.add(db_share)
    db.commit()
    db.refresh(db_share)

    return db_share


@router.patch("/shares/{share_id}", response_model=DocumentShareResponse)
async def update_document_share(
    share_id: UUID,
    share_data: DocumentShareUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service)
):
    """
    Update a document share (change permission level or expiration).

    Requires admin access to the document.
    """
    share = db.query(DocumentShare).filter(DocumentShare.id == share_id).first()
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found"
        )

    # Get document
    document = db.query(Document).filter(Document.id == share.document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check admin access to document
    if not permission_service.can_access_document(current_user, document, PermissionLevel.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to modify this share"
        )

    # Update fields if provided
    if share_data.permission_level is not None:
        if share_data.permission_level not in [
            PermissionLevel.READ,
            PermissionLevel.WRITE,
            PermissionLevel.ADMIN
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid permission level. Must be 'read', 'write', or 'admin'"
            )
        share.permission_level = share_data.permission_level

    if share_data.expires_at is not None:
        share.expires_at = share_data.expires_at

    db.commit()
    db.refresh(share)

    return share


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_share(
    share_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service)
):
    """
    Revoke a document share.

    Requires admin access to the document.
    """
    share = db.query(DocumentShare).filter(DocumentShare.id == share_id).first()
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found"
        )

    # Get document
    document = db.query(Document).filter(Document.id == share.document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check admin access to document
    if not permission_service.can_access_document(current_user, document, PermissionLevel.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to revoke this share"
        )

    db.delete(share)
    db.commit()


@router.get("/shared-with-me", response_model=List[SharedDocumentResponse])
async def list_shared_documents(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all documents shared with the current user.

    Returns documents with share information.
    """
    from sqlalchemy import and_

    # Get shares for current user that haven't expired
    shares = (
        db.query(DocumentShare)
        .filter(
            and_(
                DocumentShare.shared_with_user_id == current_user.id,
                or_(
                    DocumentShare.expires_at.is_(None),
                    DocumentShare.expires_at > datetime.utcnow()
                )
            )
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Build response with document and share info
    result = []
    for share in shares:
        document = db.query(Document).filter(Document.id == share.document_id).first()
        if document:
            result.append({
                "document": document,
                "share": share
            })

    return result


# Import or_ for expired share filtering
from sqlalchemy import or_
