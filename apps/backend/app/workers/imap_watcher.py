"""IMAP watcher worker for monitoring mailboxes."""
import email
import hashlib
import imaplib
import logging
import time
from datetime import datetime
from email.header import decode_header
from email.message import Message
from enum import StrEnum
from typing import Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError, InvalidDocumentError
from app.database import SessionLocal
from app.models.import_source import ImportSource, ImportSourceStatus, ImportSourceType
from app.services.document_intake import ALLOWED_EXTENSIONS, DocumentIntakeService
from app.services.import_failure_service import ImportFailureService

logger = logging.getLogger(__name__)


class AttachmentOutcome(StrEnum):
    """What became of one attachment on one pass over its message."""

    IMPORTED = "imported"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    DEFERRED = "deferred"


def message_is_complete(outcomes: Iterable[AttachmentOutcome]) -> bool:
    """Whether a message may be marked read or moved.

    Every attachment must have settled: taken into the archive, already held by
    it, or written down as a terminal failure. One that settled on neither —
    storage away, the database away — leaves the message where it is, so the
    next pass offers it again. See ADR 0011.
    """
    return all(outcome is not AttachmentOutcome.DEFERRED for outcome in outcomes)


class IMAPMailboxHandler:
    """Handler for IMAP mailbox monitoring."""

    def __init__(
        self,
        import_source: ImportSource,
        db: Session,
        intake_service: Optional[DocumentIntakeService] = None,
        failure_service: Optional[ImportFailureService] = None,
    ) -> None:
        """Initialize the handler.

        Args:
            import_source: Import source configuration
            db: Database session
            intake_service: Where attachment bytes become Documents
            failure_service: Where an attachment that can never become one is
                written down
        """
        self.import_source = import_source
        self.db = db
        self.intake_service = intake_service or DocumentIntakeService(db)
        self.failure_service = failure_service or ImportFailureService(db)
        self.mail: Optional[imaplib.IMAP4_SSL] = None
        self.uid_validity: str = "0"

    def connect(self) -> bool:
        """Connect to IMAP server.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Connect to IMAP server
            if self.import_source.imap_use_ssl:
                self.mail = imaplib.IMAP4_SSL(
                    self.import_source.imap_server,
                    self.import_source.imap_port or 993
                )
            else:
                self.mail = imaplib.IMAP4(
                    self.import_source.imap_server,
                    self.import_source.imap_port or 143
                )

            # Login
            self.mail.login(
                self.import_source.imap_username,
                self.import_source.imap_password
            )

            logger.info(f"Connected to IMAP server {self.import_source.imap_server}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {e}", exc_info=True)
            self.import_source.last_error = str(e)
            self.import_source.status = ImportSourceStatus.ERROR
            self.db.commit()
            return False

    def disconnect(self):
        """Disconnect from IMAP server."""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except Exception as e:
                logger.warning(f"Error disconnecting from IMAP: {e}")

    def decode_header_value(self, header_value: str) -> str:
        """Decode email header value.

        Args:
            header_value: Encoded header value

        Returns:
            Decoded string
        """
        if not header_value:
            return ""

        decoded_parts = decode_header(header_value)
        result = []

        for content, encoding in decoded_parts:
            if isinstance(content, bytes):
                try:
                    if encoding:
                        result.append(content.decode(encoding))
                    else:
                        result.append(content.decode('utf-8', errors='ignore'))
                except Exception:
                    result.append(content.decode('utf-8', errors='ignore'))
            else:
                result.append(str(content))

        return ' '.join(result)

    def extract_attachments(self, msg: Message) -> List[Tuple[str, bytes]]:
        """Extract attachments from email message.

        Args:
            msg: Email message

        Returns:
            List of filename and content pairs.
        """
        attachments = []
        for part in msg.walk():
            # Skip non-attachment parts
            if part.get_content_maintype() == 'multipart':
                continue

            # Check if this is an attachment
            filename = part.get_filename()
            if not filename:
                continue

            # Decode filename
            filename = self.decode_header_value(filename)

            # Check if file extension is allowed
            if not any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
                logger.debug(f"Skipping non-document attachment: {filename}")
                continue

            # Get file content
            content = part.get_payload(decode=True)
            if not content:
                continue

            attachments.append((filename, content))
            logger.info("Extracted attachment: %s", filename)

        return attachments

    @staticmethod
    def _message_body(data: Optional[list]) -> Optional[bytes]:
        """The message bytes out of a FETCH response.

        A server may answer with more than the part that was asked for — an
        untagged FLAGS update alongside it, as a plain bytes element — and it
        need not come last. The literal is the first element that arrives as a
        (descriptor, payload) pair.
        """
        for item in data or []:
            if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes):
                return item[1]
        return None

    def message_key(self, msg: Message, uid: bytes) -> str:
        """The identity this message keeps across passes.

        Its Message-Id where it has one: that survives a reconnect, a move to
        the processed folder and a mailbox rebuilt under a new UIDVALIDITY. The
        UID is the fallback, qualified by the UIDVALIDITY that scopes it.
        """
        header = self.decode_header_value(msg.get("Message-Id", "")).strip()
        if header:
            return header
        return f"uid:{self.uid_validity}:{uid.decode('ascii', errors='replace')}"

    def process_email(self, uid: bytes) -> bool:
        """Process a single email and import its attachments.

        Args:
            uid: The message's IMAP UID

        Returns:
            True when every attachment settled and the message may be completed,
            False when something must be tried again.
        """
        try:
            # Fetch by UID, which a concurrent expunge cannot renumber, and with
            # BODY.PEEK so that reading the message does not flag it \Seen. A
            # plain RFC822 fetch does, which would complete every message the
            # moment it was read and lose the ones this pass defers.
            status, data = self.mail.uid('FETCH', uid, '(BODY.PEEK[])')
            raw_email = self._message_body(data) if status == 'OK' else None
            if raw_email is None:
                logger.error(f"Failed to fetch email {uid}")
                return False

            msg = email.message_from_bytes(raw_email)

            # Get email subject for logging
            subject = self.decode_header_value(msg.get('Subject', 'No Subject'))
            logger.info(f"Processing email: {subject}")

            # Extract attachments
            attachments = self.extract_attachments(msg)

            if not attachments:
                logger.debug(f"No valid attachments found in email: {subject}")
                return True

            key = self.message_key(msg, uid)
            given_up_on = self.failure_service.recorded_checksums(
                import_source_id=self.import_source.id, message_key=key
            )

            outcomes = [
                self.import_attachment(filename, content, key, given_up_on)
                for filename, content in attachments
            ]

            complete = message_is_complete(outcomes)
            if not complete:
                logger.warning(
                    "Leaving email %s unprocessed: %s",
                    subject,
                    ", ".join(
                        filename
                        for (filename, _), outcome in zip(attachments, outcomes)
                        if outcome is AttachmentOutcome.DEFERRED
                    ),
                )
            return complete

        except Exception as e:
            logger.error(f"Error processing email {uid}: {e}", exc_info=True)
            return False

    def import_attachment(
        self,
        filename: str,
        content: bytes,
        message_key: str,
        given_up_on: Optional[set[str]] = None,
    ) -> AttachmentOutcome:
        """Import an attachment as a document.

        Args:
            filename: Original filename
            content: File content
            message_key: The identity of the message it arrived on
            given_up_on: Checksums already written down as terminal failures

        Returns:
            What became of the attachment.
        """
        checksum = hashlib.sha256(content).hexdigest()
        if given_up_on and checksum in given_up_on:
            logger.info(
                "Skipping attachment %s: recorded as a terminal failure", filename
            )
            return AttachmentOutcome.REJECTED

        try:
            document = self.intake_service.intake(
                content=content,
                filename=filename,
                owner_id=self.import_source.owner_id,
            )
        except DuplicateError as error:
            logger.info(
                "Duplicate Document: %s matches existing Document %s",
                filename,
                error.detail["document_id"],
            )
            return AttachmentOutcome.DUPLICATE
        except InvalidDocumentError as error:
            # These bytes will never become a Document, so offering the message
            # again would only repeat the refusal. Write it down instead, and
            # only then let the message finish.
            return self._give_up(filename, checksum, message_key, str(error))
        except Exception as error:
            logger.error(
                "Failed to import attachment %s: %s", filename, error, exc_info=True
            )
            return AttachmentOutcome.DEFERRED

        logger.info("Created Document %s from IMAP attachment %s", document.id, filename)
        return AttachmentOutcome.IMPORTED

    def _give_up(
        self, filename: str, checksum: str, message_key: str, error: str
    ) -> AttachmentOutcome:
        """Record a terminal failure; defer when it could not be recorded."""
        recorded = self.failure_service.record(
            import_source_id=self.import_source.id,
            message_key=message_key,
            filename=filename,
            checksum=checksum,
            error=error,
        )
        if recorded is None:
            logger.error(
                "Attachment %s was refused and could not be recorded; "
                "leaving its message for another pass",
                filename,
            )
            return AttachmentOutcome.DEFERRED
        logger.error("Attachment %s will not be imported: %s", filename, error)
        return AttachmentOutcome.REJECTED

    def complete_email(self, uid: bytes) -> bool:
        """Mark a finished message read, or move it to the processed folder.

        Returns:
            True when the mailbox took the change. A message whose move or flag
            failed is left as it is, so the next pass offers it again.
        """
        if self.import_source.imap_processed_folder:
            return self.move_processed_email(uid)

        try:
            status, _ = self.mail.uid('STORE', uid, '+FLAGS', '\\Seen')
        except Exception as e:
            logger.error(f"Error marking email {uid} read: {e}", exc_info=True)
            return False
        if status != 'OK':
            logger.warning(f"Failed to mark email {uid} read")
            return False
        return True

    def move_processed_email(self, uid: bytes) -> bool:
        """Move email to processed folder.

        Args:
            uid: The message's IMAP UID

        Returns:
            True if the copy was made and the original flagged for deletion.
        """
        if not self.import_source.imap_processed_folder:
            return False

        try:
            # Copy to processed folder
            result = self.mail.uid(
                'COPY', uid, self.import_source.imap_processed_folder
            )
            if result[0] != 'OK':
                # The copy failed, so deleting the original would lose the message.
                logger.warning(f"Failed to move email {uid}: {result}")
                return False

            # Mark for deletion from current folder. A refused flag leaves the
            # original in place: reporting the move as done would expunge
            # nothing and copy the message again on every pass that follows.
            status, _ = self.mail.uid('STORE', uid, '+FLAGS', '\\Deleted')
            if status != 'OK':
                logger.warning(f"Copied email {uid} but could not flag the original")
                return False
            logger.info(f"Moved email {uid} to {self.import_source.imap_processed_folder}")
            return True
        except Exception as e:
            logger.error(f"Error moving email {uid}: {e}", exc_info=True)
            return False

    def check_mailbox(self):
        """Check mailbox for new emails and process attachments."""
        try:
            # Select mailbox
            mailbox = self.import_source.imap_mailbox or 'INBOX'
            status, messages = self.mail.select(mailbox)

            if status != 'OK':
                logger.error(f"Failed to select mailbox {mailbox}")
                return

            self.uid_validity = self._selected_uid_validity()

            # Search for unread emails
            status, data = self.mail.uid('SEARCH', None, 'UNSEEN')
            if status != 'OK':
                logger.error("Failed to search for emails")
                return

            uids = data[0].split()
            logger.info(f"Found {len(uids)} unread emails in {mailbox}")

            # Process each email
            moved = False
            waiting = 0
            for uid in uids:
                try:
                    if self.process_email(uid):
                        if not self.complete_email(uid):
                            waiting += 1
                        else:
                            moved = True
                    else:
                        waiting += 1
                except Exception as e:
                    logger.error(f"Error processing email {uid}: {e}", exc_info=True)
                    waiting += 1

            # Expunge messages the move flagged for deletion
            if moved and self.import_source.imap_processed_folder:
                self.mail.expunge()

            # Update last_run timestamp. A message left for another pass is not
            # an error the source should stop for, but it is the one thing an
            # operator needs to see: clearing last_error would hide it.
            self.import_source.last_run = datetime.utcnow()
            self.import_source.last_error = (
                f"{waiting} message(s) left unprocessed; see the log" if waiting else None
            )
            self.db.commit()

        except Exception as e:
            logger.error(f"Error checking mailbox: {e}", exc_info=True)
            self.import_source.last_error = str(e)
            self.import_source.status = ImportSourceStatus.ERROR
            self.db.commit()

    def _selected_uid_validity(self) -> str:
        """The UIDVALIDITY of the mailbox just selected, or "0" if unreported."""
        try:
            _, values = self.mail.response('UIDVALIDITY')
        except Exception:
            return "0"
        if not values or not values[0]:
            return "0"
        value = values[0]
        if isinstance(value, bytes):
            return value.decode('ascii', errors='replace')
        return str(value)


class IMAPWatcherWorker:
    """Worker that monitors IMAP mailboxes for new documents."""

    def __init__(self):
        """Initialize the worker."""
        self.db = SessionLocal()
        self.check_interval = 60  # Check every 60 seconds

    def start(self):
        """Start monitoring all active IMAP import sources."""
        logger.info("Starting IMAP watcher worker")

        try:
            while True:
                # Get all active IMAP import sources
                sources = self.db.query(ImportSource).filter(
                    ImportSource.source_type == ImportSourceType.IMAP,
                    ImportSource.status == ImportSourceStatus.ACTIVE
                ).all()

                logger.info(f"Checking {len(sources)} active IMAP sources")

                for source in sources:
                    try:
                        self.check_source(source)
                    except Exception as e:
                        logger.error(f"Error checking IMAP source {source.id}: {e}", exc_info=True)
                        source.last_error = str(e)
                        source.status = ImportSourceStatus.ERROR
                        self.db.commit()

                # Sleep before next check
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("Shutting down IMAP watcher worker")
            self.stop()
        except Exception as e:
            logger.error(f"IMAP watcher worker error: {e}", exc_info=True)
            self.stop()
            raise

    def check_source(self, source: ImportSource):
        """Check a single IMAP source for new emails.

        Args:
            source: Import source to check
        """
        logger.info(f"Checking IMAP source {source.id}: {source.name}")

        handler = IMAPMailboxHandler(source, self.db)

        try:
            # Connect to IMAP server
            if not handler.connect():
                return

            # Check mailbox
            handler.check_mailbox()

        finally:
            # Always disconnect
            handler.disconnect()

    def stop(self):
        """Stop the worker."""
        logger.info("Stopping IMAP watcher worker")
        self.db.close()


def run_imap_watcher():
    """Entry point for the IMAP watcher worker."""
    worker = IMAPWatcherWorker()
    worker.start()


if __name__ == "__main__":
    run_imap_watcher()
