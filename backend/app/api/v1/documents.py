"""Document API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError, NotFoundError
from app.core.permissions import (
    PermissionLevel,
    require_document_access,
    get_permission_service,
    PermissionService,
    SystemPermissions,
    require_permission
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document
from app.schemas.document import DocumentResponse, DocumentUpdate
from app.services.document_service import DocumentService
from app.services.notification_service import notification_service

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

        # Notify document creation
        await notification_service.notify_document_created(document.id, current_user.id)

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
    description="Get a paginated list of accessible documents"
)
def list_documents(
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    current_user: User = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    db: Session = Depends(get_db)
) -> List[DocumentResponse]:
    """
    Get list of documents accessible to the current user.

    Includes:
    - Documents owned by the user
    - Public documents
    - Documents shared with the user

    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        sort_by: Field to sort by (created_at, title, file_size, processing_status)
        sort_order: Sort order (asc or desc)
    """
    if limit > 1000:
        limit = 1000  # Max limit

    # Validate sort field
    allowed_sort_fields = {
        'created_at': Document.created_at,
        'updated_at': Document.updated_at,
        'title': Document.title,
        'file_size': Document.file_size,
        'processing_status': Document.processing_status,
        'original_filename': Document.original_filename
    }

    sort_field = allowed_sort_fields.get(sort_by, Document.created_at)

    # Use permission service to get accessible documents
    query = permission_service.get_accessible_documents_query(current_user)

    # Apply sorting
    if sort_order.lower() == 'asc':
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    documents = query.offset(skip).limit(limit).all()

    return documents


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
    description="Get details for a specific document"
)
def get_document(
    document_id: UUID,
    document: Document = Depends(require_document_access(PermissionLevel.READ))
) -> DocumentResponse:
    """Get document by ID (requires read access)."""
    return document


@router.get(
    "/{document_id}/download",
    summary="Download document file",
    description="Download the original document file"
)
async def download_document(
    document_id: UUID,
    document: Document = Depends(require_document_access(PermissionLevel.READ))
):
    """Download a document file (requires read access)."""
    from fastapi.responses import FileResponse
    from app.services.storage_service import StorageService

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
    document: Document = Depends(require_document_access(PermissionLevel.WRITE))
):
    """Reprocess a document - retry OCR (requires write access)."""
    # Trigger reprocessing
    from app.tasks.document_tasks import reprocess_document as reprocess_task

    task = reprocess_task.delay(str(document_id))

    return {
        "message": "Document reprocessing triggered",
        "document_id": str(document_id),
        "task_id": task.id
    }


@router.post(
    "/{document_id}/regenerate-embeddings",
    response_model=dict,
    summary="Regenerate embeddings",
    description="Regenerate vector embeddings for a document"
)
def regenerate_embeddings(
    document_id: UUID,
    document: Document = Depends(require_document_access(PermissionLevel.WRITE))
):
    """Regenerate embeddings for a document (requires write access)."""
    # Check if document has OCR text
    if not document.ocr_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no extracted text. Run OCR first."
        )

    # Trigger embedding generation
    from app.tasks.document_tasks import generate_embeddings

    task = generate_embeddings.delay(str(document_id))

    return {
        "message": "Embedding generation triggered",
        "document_id": str(document_id),
        "task_id": task.id
    }


@router.post(
    "/{document_id}/regenerate-metadata",
    response_model=dict,
    summary="Regenerate LLM metadata",
    description="Regenerate AI-extracted metadata for a document"
)
def regenerate_metadata(
    document_id: UUID,
    document: Document = Depends(require_document_access(PermissionLevel.WRITE))
):
    """Regenerate LLM-extracted metadata for a document (requires write access)."""
    # Check if document has OCR text
    if not document.ocr_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no extracted text. Run OCR first."
        )

    # Check if LLM is enabled
    from app.config import settings
    if not settings.LLM_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM metadata extraction is disabled in configuration."
        )

    # Trigger metadata extraction
    from app.tasks.document_tasks import extract_metadata

    task = extract_metadata.delay(str(document_id))

    return {
        "message": "Metadata extraction triggered",
        "document_id": str(document_id),
        "task_id": task.id
    }


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document metadata",
    description="Update document title and other metadata"
)
async def update_document(
    document_id: UUID,
    document_update: DocumentUpdate,
    document: Document = Depends(require_document_access(PermissionLevel.WRITE)),
    db: Session = Depends(get_db)
) -> DocumentResponse:
    """Update document metadata (requires write access)."""
    # Update fields
    if document_update.title is not None:
        document.title = document_update.title
    if document_update.is_public is not None:
        document.is_public = document_update.is_public

    db.commit()
    db.refresh(document)

    # Notify document update
    await notification_service.notify_document_updated(document.id, document.owner_id)

    return document


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Delete a document and its associated files"
)
async def delete_document(
    document_id: UUID,
    document: Document = Depends(require_document_access(PermissionLevel.ADMIN)),
    db: Session = Depends(get_db)
):
    """Delete a document (requires admin access - typically owner only)."""
    from app.services.storage_service import StorageService

    # Store owner_id before deletion
    owner_id = document.owner_id

    # Delete file from storage
    try:
        storage = StorageService()
        file_path = storage.get_file_path(document.file_path)
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        # Log but don't fail the deletion
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to delete file {document.file_path}: {e}")

    # Delete database record (cascades to embeddings and shares)
    db.delete(document)
    db.commit()

    # Notify document deletion
    await notification_service.notify_document_deleted(document_id, owner_id)

    return None
