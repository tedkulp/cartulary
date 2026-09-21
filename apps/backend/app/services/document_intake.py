"""Single use case for adding source files to an Owner's archive."""

import hashlib
import logging
import uuid
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError, InvalidDocumentError
from app.models.document import OWNER_CHECKSUM_INDEX, Document
from app.processing import ProcessingStatus
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
        existing = self._existing_document(checksum, owner_id)
        if existing is not None:
            raise self._duplicate_of(existing)

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
            processing_status=ProcessingStatus.PENDING.value,
        )
        try:
            self.db.add(document)
            self.db.commit()
        except IntegrityError as error:
            # The lookup above is advisory: another intake of the same bytes may have
            # committed since. The unique index is what decides, so find the Document
            # that won the race and report the duplicate the lookup would have.
            self.db.rollback()
            self._discard(stored.relative_path)
            winner = (
                self._existing_document(checksum, owner_id)
                if self._checksum_conflict(error)
                else None
            )
            if winner is None:
                logger.exception("Document %s could not be inserted", document_id)
                raise
            raise self._duplicate_of(winner) from None
        except Exception:
            self.db.rollback()
            self._discard(stored.relative_path)
            raise
        try:
            self.enqueue(str(document.id))
        except Exception as error:
            logger.exception("Failed to queue processing for Document %s", document.id)
            document.processing_status = ProcessingStatus.FAILED.value
            document.processing_error = f"Processing could not be queued: {error}"
            try:
                self.db.commit()
            except Exception:
                logger.exception(
                    "Failed to persist queue failure for Document %s", document_id
                )
                self.db.rollback()
                document.processing_status = ProcessingStatus.FAILED.value
                document.processing_error = f"Processing could not be queued: {error}"

        try:
            self.notify(document_id, owner_id, uploader_id)
        except Exception:
            logger.exception("Failed to publish creation of Document %s", document_id)
        return document

    def _existing_document(
        self, checksum: str, owner_id: UUID
    ) -> Optional[Document]:
        """The Document already holding these bytes for this Owner, if there is one."""
        return self.db.query(Document).filter(
            Document.checksum == checksum,
            Document.owner_id == owner_id,  # not an access check: deduplication
        ).first()

    @staticmethod
    def _checksum_conflict(error: IntegrityError) -> bool:
        """Whether the per-Owner checksum index is what refused the insert.

        A foreign key to a User deleted mid-intake is not a duplicate, and must not
        be reported as one. A driver that names no constraint leaves the question to
        the lookup that follows.
        """
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        return constraint in {None, OWNER_CHECKSUM_INDEX}

    @staticmethod
    def _duplicate_of(existing: Document) -> DuplicateError:
        return DuplicateError(
            "Document already exists", detail={"document_id": str(existing.id)}
        )

    def _discard(self, relative_path: str) -> None:
        try:
            self.storage.delete_file(relative_path)
        except Exception:
            logger.exception("Failed to remove stored file after database failure")
