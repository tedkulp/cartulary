"""Document service for handling document operations."""
from typing import List, Optional
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError, NotFoundError
from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentResponse
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

        # Check for duplicates
        existing = self.db.query(Document).filter(
            Document.checksum == checksum,
            Document.owner_id == user_id
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

        # Save file to storage
        file_path = await self.storage.save_file(file, document_id, filename)

        # Get file size
        file_size = self.storage.get_file_size(file_path)

        # Create database record
        db_document = Document(
            id=document_id,
            title=doc_title,
            original_filename=filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
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

    def get_document(self, document_id: UUID, user_id: UUID) -> DocumentResponse:
        """
        Get a document by ID.

        Args:
            document_id: Document ID
            user_id: User ID (for permission check)

        Returns:
            Document

        Raises:
            NotFoundError: If document not found or user doesn't have access
        """
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.owner_id == user_id  # Simple ownership check for now
        ).first()

        if not document:
            raise NotFoundError("Document not found")

        return DocumentResponse.model_validate(document)

    def list_documents(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50
    ) -> List[DocumentResponse]:
        """
        List documents for a user.

        Args:
            user_id: User ID
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            List of documents
        """
        documents = self.db.query(Document).filter(
            Document.owner_id == user_id
        ).order_by(
            Document.created_at.desc()
        ).offset(skip).limit(limit).all()

        return [DocumentResponse.model_validate(doc) for doc in documents]

    def update_document(
        self,
        document_id: UUID,
        user_id: UUID,
        document_update: "DocumentUpdate"
    ) -> DocumentResponse:
        """
        Update document metadata.

        Args:
            document_id: Document ID
            user_id: User ID (for permission check)
            document_update: Updated document fields

        Returns:
            Updated document

        Raises:
            NotFoundError: If document not found or user doesn't have permission
        """
        from app.schemas.document import DocumentUpdate

        # Get document
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.owner_id == user_id
        ).first()

        if not document:
            raise NotFoundError("Document not found")

        # Update fields
        if document_update.title is not None:
            document.title = document_update.title
        if document_update.description is not None:
            document.description = document_update.description

        self.db.commit()
        self.db.refresh(document)

        return DocumentResponse.model_validate(document)

    def delete_document(self, document_id: UUID, user_id: UUID) -> bool:
        """
        Delete a document.

        Args:
            document_id: Document ID
            user_id: User ID (for permission check)

        Returns:
            True if deleted

        Raises:
            NotFoundError: If document not found or user doesn't have access
        """
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.owner_id == user_id
        ).first()

        if not document:
            raise NotFoundError("Document not found")

        # Delete file from storage
        if document.file_path:
            self.storage.delete_file(document.file_path)

        # Delete database record
        self.db.delete(document)
        self.db.commit()

        return True
