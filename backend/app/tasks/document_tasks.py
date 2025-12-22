"""Celery tasks for document processing."""
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document
from app.services.ocr_service import OCRService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.process_document")
def process_document(self, document_id: str) -> dict:
    """
    Process a document: extract text via OCR and update database.

    Args:
        document_id: UUID of the document to process

    Returns:
        Processing result dict with status and metadata
    """
    db: Session = SessionLocal()
    try:
        # Get document from database
        doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
        if not doc:
            logger.error(f"Document not found: {document_id}")
            return {"status": "error", "message": "Document not found"}

        # Update status to processing
        doc.processing_status = "processing"
        db.commit()

        logger.info(f"Processing document {document_id}: {doc.original_filename}")

        # Initialize OCR service
        ocr_service = OCRService()

        # Extract text
        extracted_text = ocr_service.extract_text(doc.file_path)

        if extracted_text and len(extracted_text.strip()) > 0:
            doc.ocr_text = extracted_text
            doc.ocr_language = ocr_service.detect_language(extracted_text)
            doc.processing_status = "ocr_complete"
            logger.info(
                f"Extracted {len(extracted_text)} characters from {doc.original_filename}"
            )
        else:
            logger.warning(f"No text extracted from {doc.original_filename}")
            doc.ocr_text = ""
            # Mark as pending for retry or manual processing
            doc.processing_status = "ocr_failed"
            doc.processing_error = "No text could be extracted from document"

        # Count pages if PDF
        if doc.file_path.endswith(".pdf"):
            try:
                import fitz

                pdf_doc = fitz.open(doc.file_path)
                doc.page_count = len(pdf_doc)
                pdf_doc.close()
            except Exception as e:
                logger.error(f"Failed to count PDF pages: {e}")

        db.commit()

        logger.info(
            f"Processed document {document_id} with status: {doc.processing_status}"
        )

        return {
            "status": "success",
            "document_id": document_id,
            "text_length": len(extracted_text) if extracted_text else 0,
            "page_count": doc.page_count,
        }

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}", exc_info=True)

        # Update document with error status
        try:
            doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
            if doc:
                doc.processing_status = "failed"
                doc.processing_error = str(e)
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update error status: {db_error}")

        return {"status": "error", "document_id": document_id, "message": str(e)}

    finally:
        db.close()


@celery_app.task(name="app.tasks.reprocess_document")
def reprocess_document(document_id: str) -> dict:
    """
    Reprocess a document (useful for retrying failed processing).

    Args:
        document_id: UUID of the document to reprocess

    Returns:
        Processing result dict
    """
    logger.info(f"Reprocessing document {document_id}")
    return process_document(document_id)
