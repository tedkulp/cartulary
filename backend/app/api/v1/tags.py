"""Tag API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.database import get_db
from app.models.document import Document
from app.models.tag import Tag
from app.models.user import User
from app.schemas.tag import DocumentTagRequest, TagCreate, TagResponse, TagUpdate

router = APIRouter(prefix="/tags", tags=["tags"])


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag: TagCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TagResponse:
    """
    Create a new tag.

    - **name**: Tag name (unique)
    - **color**: Hex color code (optional)
    - **description**: Tag description (optional)
    """
    # Check if tag already exists
    existing = db.query(Tag).filter(Tag.name == tag.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Tag already exists"
        )

    # Create tag
    db_tag = Tag(
        name=tag.name,
        color=tag.color,
        description=tag.description,
        created_by=current_user.id,
    )

    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)

    return TagResponse.model_validate(db_tag)


@router.get("", response_model=List[TagResponse])
async def list_tags(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TagResponse]:
    """
    List all tags.

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    tags = (
        db.query(Tag).order_by(Tag.name).offset(skip).limit(limit).all()
    )

    return [TagResponse.model_validate(tag) for tag in tags]


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TagResponse:
    """
    Get a tag by ID.
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise NotFoundError("Tag not found")

    return TagResponse.model_validate(tag)


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: UUID,
    tag_update: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TagResponse:
    """
    Update a tag.

    - **name**: New tag name (optional)
    - **color**: New hex color code (optional)
    - **description**: New description (optional)
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise NotFoundError("Tag not found")

    # Update fields
    if tag_update.name is not None:
        # Check for name conflict
        existing = (
            db.query(Tag)
            .filter(Tag.name == tag_update.name, Tag.id != tag_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tag name already exists",
            )
        tag.name = tag_update.name

    if tag_update.color is not None:
        tag.color = tag_update.color

    if tag_update.description is not None:
        tag.description = tag_update.description

    db.commit()
    db.refresh(tag)

    return TagResponse.model_validate(tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a tag.
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise NotFoundError("Tag not found")

    db.delete(tag)
    db.commit()


@router.post("/documents/{document_id}/tags", response_model=dict)
async def add_tags_to_document(
    document_id: UUID,
    tag_request: DocumentTagRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Add tags to a document.

    - **tag_ids**: List of tag IDs to add
    """
    # Get document
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner_id == current_user.id)
        .first()
    )

    if not document:
        raise NotFoundError("Document not found")

    # Get tags
    tags = db.query(Tag).filter(Tag.id.in_(tag_request.tag_ids)).all()

    if len(tags) != len(tag_request.tag_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="One or more tags not found"
        )

    # Add tags to document
    for tag in tags:
        if tag not in document.tags:
            document.tags.append(tag)

    db.commit()

    return {"message": "Tags added successfully", "tag_count": len(tags)}


@router.delete("/documents/{document_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tag_from_document(
    document_id: UUID,
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a tag from a document.
    """
    # Get document
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner_id == current_user.id)
        .first()
    )

    if not document:
        raise NotFoundError("Document not found")

    # Get tag
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise NotFoundError("Tag not found")

    # Remove tag from document
    if tag in document.tags:
        document.tags.remove(tag)
        db.commit()
