"""Document service for handling document operations."""
from typing import Optional
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError
from app.models.document import Document
from app.schemas.document import DocumentResponse
from app.services.storage_service import StorageService


class DocumentService:
    """Service for handling document operations."""

    def __init__(self, db: Session, storage: Optional[StorageService] = None):
        """
        Initialize document service.

        Args:
            db: Database session
            storage: Storage service (will create default if not provided)
        """
        self.db = db
        self.storage = storage or StorageService()

    async def create_document(
        self,
        file: UploadFile,
        user_id: UUID,
        title: Optional[str] = None
    ) -> DocumentResponse:
        """
        Create a new document from uploaded file.

        Args:
            file: Uploaded file
            user_id: Owner user ID
            title: Optional document title (defaults to filename)

        Returns:
            Created document

        Raises:
            DuplicateError: If document with same checksum already exists
        """
        # Calculate checksum for deduplication
        checksum = await self.storage.calculate_checksum(file)

        # Check for duplicates. Deduplication is per owner, not an access
        # decision, so this is the one owner comparison outside the access filter.
        existing = self.db.query(Document).filter(
            Document.checksum == checksum,
            Document.owner_id == user_id,  # not an access check: deduplication
        ).first()

        if existing:
            raise DuplicateError(
                f"Document already exists",
                detail={"document_id": str(existing.id)}
            )

        # Create document record
        import uuid
        document_id = uuid.uuid4()

        # Use provided title or fall back to filename
        doc_title = title or file.filename or "Untitled"

        # Get filename
        filename = file.filename or "document"

        # Save file to storage (images are automatically converted to PDF)
        file_path, final_filename, mime_type = await self.storage.save_file(file, document_id, filename)

        # Get file size
        file_size = self.storage.get_file_size(file_path)

        # Create database record
        db_document = Document(
            id=document_id,
            title=doc_title,
            original_filename=filename,  # Keep original filename for user reference
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,  # Use the actual MIME type (will be application/pdf for converted images)
            checksum=checksum,
            owner_id=user_id,
            uploaded_by=user_id,  # Track who uploaded the file
            processing_status="pending"  # Will be processed by background task
        )

        self.db.add(db_document)
        self.db.commit()
        self.db.refresh(db_document)

        # Trigger background processing
        from app.tasks.document_tasks import process_document

        process_document.delay(str(db_document.id))

        return DocumentResponse.model_validate(db_document)
