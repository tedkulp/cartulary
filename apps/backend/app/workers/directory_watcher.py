"""Directory watcher worker for monitoring import sources."""
import logging
import time
from pathlib import Path
from typing import Dict, Set
from datetime import datetime
from uuid import UUID
import hashlib

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.import_source import ImportSource, ImportSourceType, ImportSourceStatus
from app.models.document import Document
from app.tasks.document_tasks import process_document
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class DocumentFileHandler(FileSystemEventHandler):
    """Handler for document file system events."""

    def __init__(self, import_source_id: str, db: Session):
        """Initialize the handler.

        Args:
            import_source_id: UUID of the import source
            db: Database session
        """
        super().__init__()
        self.import_source_id = import_source_id
        self.db = db
        self.processing_files: Set[str] = set()

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = event.src_path

        # Skip if already processing
        if file_path in self.processing_files:
            return

        # Only process PDF and image files
        allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}
        if not any(file_path.lower().endswith(ext) for ext in allowed_extensions):
            logger.debug(f"Skipping non-document file: {file_path}")
            return

        # Wait a bit to ensure file is fully written
        time.sleep(2)

        try:
            self.processing_files.add(file_path)
            logger.info(f"Processing new file from import source {self.import_source_id}: {file_path}")

            # Get import source to determine owner
            source = self.db.query(ImportSource).filter(
                ImportSource.id == self.import_source_id
            ).first()

            if not source:
                logger.error(f"Import source {self.import_source_id} not found")
                return

            # Read file and calculate checksum
            with open(file_path, 'rb') as f:
                file_content = f.read()

            checksum = hashlib.sha256(file_content).hexdigest()

            # Check for duplicates
            existing = self.db.query(Document).filter(
                Document.checksum == checksum,
                Document.owner_id == source.owner_id
            ).first()

            if existing:
                logger.info(f"Duplicate document found: {file_path} matches existing document {existing.id}")
                # Handle post-import actions for duplicate
                if source.move_after_import and source.move_to_path:
                    filename = Path(file_path).name
                    move_to = Path(source.move_to_path) / filename
                    move_to.parent.mkdir(parents=True, exist_ok=True)
                    Path(file_path).rename(move_to)
                    logger.info(f"Moved duplicate file to: {move_to}")
                elif source.delete_after_import:
                    Path(file_path).unlink()
                    logger.info(f"Deleted duplicate file: {file_path}")
                return

            # Get filename
            filename = Path(file_path).name

            # Import storage service to save file
            from app.services.storage_service import StorageService
            import uuid
            import shutil

            storage = StorageService()
            document_id = uuid.uuid4()

            # Copy file to storage location
            doc_path = storage._get_document_path(document_id)
            storage_path = doc_path / filename
            shutil.copy2(file_path, storage_path)

            # Convert images to PDF
            if storage._is_image_file(filename):
                logger.info(f"Image file detected in import, converting to PDF: {filename}")
                pdf_path = storage._convert_image_to_pdf(storage_path)
                final_storage_path = pdf_path
                final_filename = pdf_path.name
                mime_type = "application/pdf"
            else:
                final_storage_path = storage_path
                final_filename = filename
                # Detect mime type
                import mimetypes
                mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

            # Get file size
            file_size = final_storage_path.stat().st_size

            # Get relative path
            relative_path = str(final_storage_path.relative_to(storage.base_path))

            # Create document record
            document = Document(
                id=document_id,
                title=filename,
                original_filename=filename,
                file_path=relative_path,
                checksum=checksum,
                file_size=file_size,
                mime_type=mime_type,
                owner_id=source.owner_id,
                processing_status="pending"
            )

            self.db.add(document)
            self.db.commit()

            logger.info(f"Created document {document_id} from {filename}")

            # Notify document creation
            notification_service.notify_document_created_sync(document_id, source.owner_id)

            # Queue processing task
            process_document.delay(str(document_id))

            # Handle post-import actions
            if source.move_after_import and source.move_to_path:
                # Move file to processed directory
                move_to = Path(source.move_to_path) / filename
                move_to.parent.mkdir(parents=True, exist_ok=True)
                Path(file_path).rename(move_to)
                logger.info(f"Moved file to: {move_to}")
            elif source.delete_after_import:
                # Delete file after import
                Path(file_path).unlink()
                logger.info(f"Deleted file: {file_path}")

            # Update last_run timestamp
            source.last_run = datetime.utcnow()
            source.last_error = None
            self.db.commit()

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}", exc_info=True)

            # Update error status
            try:
                source = self.db.query(ImportSource).filter(
                    ImportSource.id == self.import_source_id
                ).first()
                if source:
                    source.last_error = str(e)
                    source.status = ImportSourceStatus.ERROR
                    self.db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update error status: {db_error}")
        finally:
            self.processing_files.discard(file_path)


class DirectoryWatcherWorker:
    """Worker that monitors directories for new documents."""

    def __init__(self):
        """Initialize the worker."""
        self.observers: Dict[str, Observer] = {}
        self.db = SessionLocal()

    def start(self):
        """Start monitoring all active directory import sources."""
        logger.info("Starting directory watcher worker")

        try:
            while True:
                # Get all active directory import sources
                sources = self.db.query(ImportSource).filter(
                    ImportSource.source_type == ImportSourceType.DIRECTORY,
                    ImportSource.status == ImportSourceStatus.ACTIVE
                ).all()

                # Track active source IDs
                active_source_ids = set()

                for source in sources:
                    active_source_ids.add(str(source.id))

                    # Skip if already watching
                    if str(source.id) in self.observers:
                        continue

                    # Validate watch path
                    if not source.watch_path:
                        logger.warning(f"Import source {source.id} has no watch_path")
                        continue

                    watch_path = Path(source.watch_path)
                    if not watch_path.exists():
                        logger.warning(f"Watch path does not exist: {watch_path}")
                        source.last_error = f"Watch path does not exist: {watch_path}"
                        source.status = ImportSourceStatus.ERROR
                        self.db.commit()
                        continue

                    # Create observer for this source
                    try:
                        event_handler = DocumentFileHandler(str(source.id), self.db)
                        observer = Observer()
                        observer.schedule(event_handler, str(watch_path), recursive=False)
                        observer.start()

                        self.observers[str(source.id)] = observer
                        logger.info(f"Started watching {watch_path} for import source {source.id}")
                    except Exception as e:
                        logger.error(f"Failed to start observer for {source.id}: {e}")
                        source.last_error = str(e)
                        source.status = ImportSourceStatus.ERROR
                        self.db.commit()

                # Stop observers for sources that are no longer active
                for source_id in list(self.observers.keys()):
                    if source_id not in active_source_ids:
                        logger.info(f"Stopping observer for inactive source {source_id}")
                        observer = self.observers.pop(source_id)
                        observer.stop()
                        observer.join()

                # Sleep for a bit before checking for new sources
                time.sleep(60)

        except KeyboardInterrupt:
            logger.info("Shutting down directory watcher worker")
            self.stop()
        except Exception as e:
            logger.error(f"Directory watcher worker error: {e}", exc_info=True)
            self.stop()
            raise

    def stop(self):
        """Stop all observers."""
        logger.info("Stopping all directory observers")
        for observer in self.observers.values():
            observer.stop()
            observer.join()
        self.observers.clear()
        self.db.close()


def run_directory_watcher():
    """Entry point for the directory watcher worker."""
    worker = DirectoryWatcherWorker()
    worker.start()


if __name__ == "__main__":
    run_directory_watcher()
