"""IMAP watcher worker for monitoring mailboxes."""
import logging
import time
import email
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from email.message import Message
from email.header import decode_header
import imaplib
import uuid

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.import_source import ImportSource, ImportSourceType, ImportSourceStatus
from app.models.document import Document
from app.tasks.document_tasks import process_document
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class IMAPMailboxHandler:
    """Handler for IMAP mailbox monitoring."""

    def __init__(self, import_source: ImportSource, db: Session):
        """Initialize the handler.

        Args:
            import_source: Import source configuration
            db: Database session
        """
        self.import_source = import_source
        self.db = db
        self.storage = StorageService()
        self.mail: Optional[imaplib.IMAP4_SSL] = None

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

    def extract_attachments(self, msg: Message) -> List[Tuple[str, bytes, str]]:
        """Extract attachments from email message.

        Args:
            msg: Email message

        Returns:
            List of tuples (filename, content, mime_type)
        """
        attachments = []
        allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}

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
            if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
                logger.debug(f"Skipping non-document attachment: {filename}")
                continue

            # Get file content
            content = part.get_payload(decode=True)
            if not content:
                continue

            # Get mime type
            mime_type = part.get_content_type()

            attachments.append((filename, content, mime_type))
            logger.info(f"Extracted attachment: {filename} ({mime_type})")

        return attachments

    def process_email(self, email_id: bytes) -> bool:
        """Process a single email and import attachments.

        Args:
            email_id: Email ID

        Returns:
            True if processing successful, False otherwise
        """
        try:
            # Fetch email
            status, data = self.mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                logger.error(f"Failed to fetch email {email_id}")
                return False

            # Parse email
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Get email subject for logging
            subject = self.decode_header_value(msg.get('Subject', 'No Subject'))
            logger.info(f"Processing email: {subject}")

            # Extract attachments
            attachments = self.extract_attachments(msg)

            if not attachments:
                logger.debug(f"No valid attachments found in email: {subject}")
                return True

            # Process each attachment
            for filename, content, mime_type in attachments:
                try:
                    self.import_attachment(filename, content, mime_type)
                except Exception as e:
                    logger.error(f"Failed to import attachment {filename}: {e}", exc_info=True)
                    # Continue with other attachments even if one fails

            return True

        except Exception as e:
            logger.error(f"Error processing email {email_id}: {e}", exc_info=True)
            return False

    def import_attachment(self, filename: str, content: bytes, mime_type: str):
        """Import an attachment as a document.

        Args:
            filename: Original filename
            content: File content
            mime_type: MIME type
        """
        # Calculate checksum
        checksum = hashlib.sha256(content).hexdigest()

        # Check for duplicates
        existing = self.db.query(Document).filter(
            Document.checksum == checksum,
            Document.owner_id == self.import_source.owner_id
        ).first()

        if existing:
            logger.info(f"Duplicate document found: {filename} matches existing document {existing.id}")
            return

        # Create document
        document_id = uuid.uuid4()

        # Save file to storage
        storage_path = self.storage.get_file_path(f"{document_id}/{filename}")
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        with open(storage_path, 'wb') as f:
            f.write(content)

        file_size = len(content)

        # Create document record
        document = Document(
            id=document_id,
            title=filename,
            original_filename=filename,
            file_path=f"{document_id}/{filename}",
            checksum=checksum,
            file_size=file_size,
            mime_type=mime_type,
            owner_id=self.import_source.owner_id,
            processing_status="pending"
        )

        self.db.add(document)
        self.db.commit()

        logger.info(f"Created document {document_id} from IMAP attachment {filename}")

        # Queue processing task
        process_document.delay(str(document_id))

    def move_processed_email(self, email_id: bytes):
        """Move email to processed folder.

        Args:
            email_id: Email ID
        """
        if not self.import_source.imap_processed_folder:
            return

        try:
            # Copy to processed folder
            result = self.mail.copy(email_id, self.import_source.imap_processed_folder)
            if result[0] == 'OK':
                # Mark for deletion from current folder
                self.mail.store(email_id, '+FLAGS', '\\Deleted')
                logger.info(f"Moved email {email_id} to {self.import_source.imap_processed_folder}")
            else:
                logger.warning(f"Failed to move email {email_id}: {result}")
        except Exception as e:
            logger.error(f"Error moving email {email_id}: {e}", exc_info=True)

    def check_mailbox(self):
        """Check mailbox for new emails and process attachments."""
        try:
            # Select mailbox
            mailbox = self.import_source.imap_mailbox or 'INBOX'
            status, messages = self.mail.select(mailbox)

            if status != 'OK':
                logger.error(f"Failed to select mailbox {mailbox}")
                return

            # Search for unread emails
            status, data = self.mail.search(None, 'UNSEEN')
            if status != 'OK':
                logger.error("Failed to search for emails")
                return

            email_ids = data[0].split()
            logger.info(f"Found {len(email_ids)} unread emails in {mailbox}")

            # Process each email
            for email_id in email_ids:
                try:
                    if self.process_email(email_id):
                        # Move to processed folder if configured
                        if self.import_source.imap_processed_folder:
                            self.move_processed_email(email_id)
                        else:
                            # Just mark as read
                            self.mail.store(email_id, '+FLAGS', '\\Seen')
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}", exc_info=True)

            # Expunge deleted messages
            if self.import_source.imap_processed_folder:
                self.mail.expunge()

            # Update last_run timestamp
            self.import_source.last_run = datetime.utcnow()
            self.import_source.last_error = None
            self.db.commit()

        except Exception as e:
            logger.error(f"Error checking mailbox: {e}", exc_info=True)
            self.import_source.last_error = str(e)
            self.import_source.status = ImportSourceStatus.ERROR
            self.db.commit()


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
