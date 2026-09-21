"""Single use case for adding source files to an Owner's archive."""

import hashlib
import logging
import uuid
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError, InvalidDocumentError
from app.models.document import Document
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}

EnqueueDocument = Callable[[str], object]
NotifyDocumentCreated = Callable[[UUID, UUID, Optional[UUID]], object]


def _enqueue_document(document_id: str) -> object:
    from app.processing import Stage
    from app.processing.queue import enqueue_stage

    return enqueue_stage(document_id, Stage.OCR)


def _notify_document_created(
    document_id: UUID, owner_id: UUID, uploader_id: Optional[UUID]
) -> object:
    from app.services.notification_service import notification_service

    return notification_service.notify_document_created_sync(
        document_id, owner_id, uploader_id
    )


class DocumentIntakeService:
    """Validate, persist and announce one Document intake."""

    def __init__(
        self,
        db: Session,
        storage: Optional[StorageService] = None,
        enqueue: EnqueueDocument = _enqueue_document,
        notify: NotifyDocumentCreated = _notify_document_created,
    ) -> None:
        self.db = db
        self.storage = storage or StorageService()
        self.enqueue = enqueue
        self.notify = notify

    def intake(
        self,
        *,
        content: bytes,
        filename: str,
        owner_id: UUID,
        uploader_id: Optional[UUID] = None,
        title: Optional[str] = None,
    ) -> Document:
        """Add source bytes to an Owner's archive."""
        canonical_filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if not content:
            raise InvalidDocumentError("Document content cannot be empty")
        if canonical_filename in {"", ".", ".."}:
            raise InvalidDocumentError("A filename is required")
        extension = "." + canonical_filename.rsplit(".", 1)[-1].lower()
        if "." not in canonical_filename or extension not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise InvalidDocumentError(f"File type not supported. Allowed: {allowed}")
        normalized_title = title.strip() if title else ""
        if len(normalized_title) > 500:
            raise InvalidDocumentError("Document title cannot exceed 500 characters")

        checksum = hashlib.sha256(content).hexdigest()
        existing = self.db.query(Document).filter(
            Document.checksum == checksum,
            Document.owner_id == owner_id,  # not an access check: deduplication
        ).first()
        if existing:
            raise DuplicateError(
                "Document already exists", detail={"document_id": str(existing.id)}
            )

        document_id = uuid.uuid4()
        try:
            stored = self.storage.save_bytes(content, document_id, canonical_filename)
        except ValueError as error:
            self.db.rollback()
            raise InvalidDocumentError(str(error)) from error
        except Exception:
            self.db.rollback()
            raise
        document = Document(
            id=document_id,
            title=normalized_title or canonical_filename,
            original_filename=canonical_filename,
            file_path=stored.relative_path,
            file_size=stored.size,
            mime_type=stored.mime_type,
            checksum=checksum,
            owner_id=owner_id,
            uploaded_by=uploader_id,
            processing_status="pending",
        )
        try:
            self.db.add(document)
            self.db.commit()
        except Exception:
            self.db.rollback()
            try:
                self.storage.delete_file(stored.relative_path)
            except Exception:
                logger.exception("Failed to remove stored file after database failure")
            raise
        try:
            self.enqueue(str(document.id))
        except Exception as error:
            logger.exception("Failed to queue processing for Document %s", document.id)
            document.processing_status = "failed"
            document.processing_error = f"Processing could not be queued: {error}"
            try:
                self.db.commit()
            except Exception:
                logger.exception(
                    "Failed to persist queue failure for Document %s", document_id
                )
                self.db.rollback()
                document.processing_status = "failed"
                document.processing_error = f"Processing could not be queued: {error}"

        try:
            self.notify(document_id, owner_id, uploader_id)
        except Exception:
            logger.exception("Failed to publish creation of Document %s", document_id)
        return document
