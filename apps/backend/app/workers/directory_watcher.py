"""Directory watcher worker - polls import source directories for new files."""
import hashlib
import logging
import mimetypes
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.database import SessionLocal
from app.models.document import Document
from app.models.import_source import ImportSource, ImportSourceStatus, ImportSourceType
from app.services.storage_service import StorageService
from app.tasks.document_tasks import process_document

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}
POLL_INTERVAL = 10  # seconds between directory scans


def _wait_for_stable_size(path: Path, check_interval: float = 2.0) -> bool:
    """Return True when the file size stops changing (write complete).
    Returns False if the file disappears before it stabilises."""
    try:
        previous = path.stat().st_size
        time.sleep(check_interval)
        return path.stat().st_size == previous
    except OSError:
        return False


def _process_file(file_path: Path, source: ImportSource, db) -> bool:
    """Import a single file.  Returns True if the file was handled (processed
    or skipped as a duplicate), False if it should be retried later."""
    with open(file_path, 'rb') as f:
        file_content = f.read()

    checksum = hashlib.sha256(file_content).hexdigest()

    # Deduplication check
    existing = db.query(Document).filter(
        Document.checksum == checksum,
        Document.owner_id == source.owner_id
    ).first()

    if existing:
        logger.info(f"Skipping duplicate file {file_path.name} (matches document {existing.id})")
        _handle_post_import(file_path, source)
        return True

    filename = file_path.name
    storage = StorageService()
    document_id = uuid.uuid4()

    doc_dir = storage._get_document_path(document_id)
    stored_path = doc_dir / filename
    shutil.copy2(file_path, stored_path)

    if storage._is_image_file(filename):
        logger.info(f"Converting image to PDF: {filename}")
        stored_path = storage._convert_image_to_pdf(stored_path)
        filename = stored_path.name
        mime_type = "application/pdf"
    else:
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    relative_path = str(stored_path.relative_to(storage.base_path))

    document = Document(
        id=document_id,
        title=file_path.name,
        original_filename=file_path.name,
        file_path=relative_path,
        checksum=checksum,
        file_size=stored_path.stat().st_size,
        mime_type=mime_type,
        owner_id=source.owner_id,
        processing_status="pending",
    )
    db.add(document)
    db.commit()

    logger.info(f"Imported {file_path.name} → document {document_id}")

    process_document.delay(str(document_id))

    _handle_post_import(file_path, source)
    return True


def _handle_post_import(file_path: Path, source: ImportSource):
    if source.move_after_import and source.move_to_path:
        dest = Path(source.move_to_path) / file_path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        file_path.rename(dest)
    elif source.delete_after_import:
        file_path.unlink()


def _scan_source(source: ImportSource, seen: set, db) -> None:
    """Scan one import source directory and process any new files."""
    watch_path = Path(source.watch_path)

    if not watch_path.exists():
        logger.warning(f"Watch path does not exist: {watch_path} (source: {source.name})")
        source.last_error = f"Watch path does not exist: {watch_path}"
        source.status = ImportSourceStatus.ERROR
        db.commit()
        return

    for file_path in sorted(watch_path.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        file_key = (source.id, str(file_path))
        if file_key in seen:
            continue

        logger.info(f"Found new file: {file_path}")

        if not _wait_for_stable_size(file_path):
            logger.debug(f"File disappeared or still writing: {file_path}")
            continue

        try:
            _process_file(file_path, source, db)
            source.last_run = datetime.utcnow()
            source.last_error = None
            db.commit()
        except Exception as e:
            logger.error(f"Error importing {file_path}: {e}", exc_info=True)
            source.last_error = str(e)
            db.commit()

        # Mark seen regardless of success so we don't retry in the same run.
        # If the file is still present next poll it will be tried again (handled
        # by checksum dedup).  If it was moved/deleted it won't appear.
        seen.add(file_key)


def run_directory_watcher():
    """Entry point: poll all active directory import sources forever."""
    logger.info("Directory watcher started (poll interval: %ds)", POLL_INTERVAL)

    # Track files we've already dealt with this session to avoid
    # hammering the DB on every poll for files that are still present.
    seen: set = set()

    while True:
        try:
            db = SessionLocal()
            try:
                sources = db.query(ImportSource).filter(
                    ImportSource.source_type == ImportSourceType.DIRECTORY,
                    ImportSource.status == ImportSourceStatus.ACTIVE,
                ).all()

                if not sources:
                    logger.debug("No active directory import sources found")
                else:
                    for source in sources:
                        if not source.watch_path:
                            continue
                        _scan_source(source, seen, db)

                # Prune seen entries for sources that no longer exist so the
                # set doesn't grow unbounded over a long run.
                active_ids = {source.id for source in sources}
                seen = {k for k in seen if k[0] in active_ids}

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Directory watcher loop error: {e}", exc_info=True)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    run_directory_watcher()
