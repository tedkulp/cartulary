"""Where an import source writes down an attachment it can never take in."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.import_failure import (
    MESSAGE_KEY_LENGTH,
    ImportFailure,
)

logger = logging.getLogger(__name__)


class ImportFailureService:
    """Record, and recall, the attachments an import source has given up on.

    Recording is what turns "this attachment failed" into a terminal outcome:
    until the row is there, the message carrying it is not finished and will be
    offered again. See ADR 0011.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        import_source_id: UUID,
        message_key: str,
        filename: str,
        checksum: str,
        error: str,
    ) -> Optional[ImportFailure]:
        """Write down one terminal failure, or find the one already written.

        Returns None when the row could not be written, which leaves the caller
        without the record it needs to complete the message.
        """
        failure = ImportFailure(
            import_source_id=import_source_id,
            message_key=self._truncate(message_key),
            filename=filename[:255],
            checksum=checksum,
            error=error,
        )
        try:
            self.db.add(failure)
            self.db.commit()
        except IntegrityError:
            # The same attachment of the same message was recorded by an earlier
            # pass, or by another watcher running beside this one. The first
            # record is the record; the outcome is terminal either way.
            self.db.rollback()
            return self._existing(import_source_id, message_key, checksum)
        except Exception:
            logger.exception(
                "Failed to record terminal import failure for %s", filename
            )
            self.db.rollback()
            return None
        return failure

    def recorded_checksums(
        self, *, import_source_id: UUID, message_key: str
    ) -> set[str]:
        """The attachment checksums this source has already given up on."""
        rows = (
            self.db.query(ImportFailure.checksum)
            .filter(
                ImportFailure.import_source_id == import_source_id,
                ImportFailure.message_key == self._truncate(message_key),
            )
            .all()
        )
        return {checksum for (checksum,) in rows}

    def _existing(
        self, import_source_id: UUID, message_key: str, checksum: str
    ) -> Optional[ImportFailure]:
        return (
            self.db.query(ImportFailure)
            .filter(
                ImportFailure.import_source_id == import_source_id,
                ImportFailure.message_key == self._truncate(message_key),
                ImportFailure.checksum == checksum,
            )
            .first()
        )

    @staticmethod
    def _truncate(message_key: str) -> str:
        return message_key[:MESSAGE_KEY_LENGTH]
