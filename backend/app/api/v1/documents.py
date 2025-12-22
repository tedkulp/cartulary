"""Document API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError, NotFoundError
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    """Get document service instance."""
    return DocumentService(db)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new document",
    description="Upload a PDF or image file for processing"
)
async def upload_document(
    file: UploadFile = File(..., description="File to upload"),
    title: str = Form(None, description="Optional document title"),
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """
    Upload a new document.

    The file will be stored and queued for OCR processing.
    """
    # Validate file type (basic check - will be more thorough in OCR phase)
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )

    # Check file extension
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
    file_ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
        )

    try:
        document = await doc_service.create_document(
            file=file,
            user_id=current_user.id,
            title=title
        )
        return document

    except DuplicateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "duplicate",
                "message": e.message,
                **e.detail
            }
        )
    except Exception as e:
        # Log the full error for debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List documents",
    description="Get a paginated list of user's documents"
)
def list_documents(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service)
) -> List[DocumentResponse]:
    """Get list of documents for the current user."""
    if limit > 100:
        limit = 100  # Max limit

    return doc_service.list_documents(
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
    description="Get details for a specific document"
)
def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Get document by ID."""
    try:
        return doc_service.get_document(
            document_id=document_id,
            user_id=current_user.id
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Delete a document and its associated files"
)
def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service)
):
    """Delete a document."""
    try:
        doc_service.delete_document(
            document_id=document_id,
            user_id=current_user.id
        )
        return None
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
