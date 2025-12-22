"""Document API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError, NotFoundError
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentUpdate
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


@router.get(
    "/{document_id}/download",
    summary="Download document file",
    description="Download the original document file"
)
async def download_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download a document file."""
    from fastapi.responses import FileResponse
    from app.services.storage_service import StorageService
    from app.models.document import Document

    # Query document directly from database to get file_path
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.owner_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Get absolute file path
    storage = StorageService()
    file_path = storage.get_file_path(document.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk"
        )

    return FileResponse(
        path=str(file_path),
        filename=document.original_filename,
        media_type=document.mime_type
    )


@router.post(
    "/{document_id}/reprocess",
    response_model=dict,
    summary="Reprocess document",
    description="Retry OCR processing for a failed or pending document"
)
def reprocess_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service)
):
    """Reprocess a document (retry OCR)."""
    try:
        # Verify document exists and user has access
        doc_service.get_document(document_id=document_id, user_id=current_user.id)

        # Trigger reprocessing
        from app.tasks.document_tasks import reprocess_document as reprocess_task

        task = reprocess_task.delay(str(document_id))

        return {
            "message": "Document reprocessing triggered",
            "document_id": str(document_id),
            "task_id": task.id
        }
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document metadata",
    description="Update document title and other metadata"
)
def update_document(
    document_id: UUID,
    document_update: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Update document metadata."""
    try:
        return doc_service.update_document(
            document_id=document_id,
            user_id=current_user.id,
            document_update=document_update
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
