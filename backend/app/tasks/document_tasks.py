"""Celery tasks for document processing."""
import logging
from uuid import UUID
from typing import List

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document, DocumentEmbedding
from app.services.ocr_service import OCRService
from app.services.embedding_service import EmbeddingService
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

        # Get absolute file path
        from app.services.storage_service import StorageService
        storage = StorageService()
        absolute_path = str(storage.get_file_path(doc.file_path))

        logger.info(f"Absolute file path: {absolute_path}")

        # Initialize OCR service
        ocr_service = OCRService()

        # Extract text
        extracted_text = ocr_service.extract_text(absolute_path)

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
        if absolute_path.endswith(".pdf"):
            try:
                import fitz

                pdf_doc = fitz.open(absolute_path)
                doc.page_count = len(pdf_doc)
                pdf_doc.close()
            except Exception as e:
                logger.error(f"Failed to count PDF pages: {e}")

        db.commit()

        logger.info(
            f"Processed document {document_id} with status: {doc.processing_status}"
        )

        # Trigger embedding generation if enabled and OCR was successful
        from app.config import settings
        if settings.EMBEDDING_ENABLED and doc.processing_status == "ocr_complete" and doc.ocr_text:
            logger.info(f"Triggering embedding generation for document {document_id}")
            generate_embeddings.delay(document_id)
        elif not settings.EMBEDDING_ENABLED:
            logger.info(f"Embedding generation disabled, skipping for document {document_id}")

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


@celery_app.task(bind=True, name="app.tasks.generate_embeddings")
def generate_embeddings(self, document_id: str) -> dict:
    """
    Generate vector embeddings for a document's text.

    Args:
        document_id: UUID of the document to generate embeddings for

    Returns:
        Processing result dict with status and embedding count
    """
    db: Session = SessionLocal()
    try:
        # Get document from database using raw SQL to avoid SQLAlchemy lazy-loading issues
        from sqlalchemy import text as sql_text
        result = db.execute(
            sql_text("SELECT ocr_text FROM documents WHERE id = :doc_id"),
            {"doc_id": document_id}
        )
        row = result.fetchone()

        if not row:
            logger.error(f"Document not found: {document_id}")
            return {"status": "error", "message": "Document not found"}

        ocr_text = row[0]
        if not ocr_text:
            logger.warning(f"No OCR text available for document {document_id}")
            return {"status": "skipped", "message": "No text to embed"}

        # Make a plain Python string copy to avoid any SQLAlchemy proxy issues
        ocr_text_copy = str(ocr_text)

        logger.info(f"Generating embeddings for document {document_id}")
        logger.info(f"Document has {len(ocr_text_copy)} characters of text")

        # Delete existing embeddings for this document
        db.query(DocumentEmbedding).filter(
            DocumentEmbedding.document_id == UUID(document_id)
        ).delete()
        db.commit()

        # Initialize embedding service with settings
        from app.config import settings

        logger.info(f"About to initialize EmbeddingService with provider={settings.EMBEDDING_PROVIDER}")

        try:
            embedding_service = EmbeddingService(
                provider=settings.EMBEDDING_PROVIDER,
                model_name=settings.EMBEDDING_MODEL,
                api_key=settings.OPENAI_API_KEY if settings.EMBEDDING_PROVIDER == "openai" else None,
                dimension=settings.EMBEDDING_DIMENSION,
            )
            logger.info(f"EmbeddingService initialized successfully")
        except Exception as init_error:
            logger.error(f"Failed to initialize EmbeddingService: {init_error}", exc_info=True)
            raise

        logger.info(f"Using {settings.EMBEDDING_PROVIDER} embeddings with model {settings.EMBEDDING_MODEL} (dimension: {settings.EMBEDDING_DIMENSION})")

        # Chunk the text
        logger.info(f"About to chunk text ({len(ocr_text_copy)} characters)")
        logger.info(f"Text type: {type(ocr_text_copy)}")
        logger.info(f"Text preview (first 100 chars): {ocr_text_copy[:100]}")
        logger.info(f"Chunk size: {settings.EMBEDDING_CHUNK_SIZE}, overlap: {settings.EMBEDDING_CHUNK_OVERLAP}")

        # CRITICAL WORKAROUND: Use simplest possible chunking to avoid mysterious hangs
        logger.info("Using simple fixed-size chunking (no rfind, no strip)...")
        chunk_size = settings.EMBEDDING_CHUNK_SIZE
        chunks = []

        logger.info(f"Starting loop: text length is {len(ocr_text_copy)}")
        i = 0
        while i < len(ocr_text_copy):
            logger.info(f"Loop iteration {len(chunks)}: i={i}")
            end = min(i + chunk_size, len(ocr_text_copy))
            chunk = ocr_text_copy[i:end]
            chunks.append(chunk)
            i = end
            logger.info(f"Added chunk {len(chunks)}, next i={i}")

        logger.info(f"✓ Loop completed, got {len(chunks)} chunks")

        if not chunks:
            logger.warning(f"No chunks generated for document {document_id}")
            return {"status": "skipped", "message": "No chunks to embed"}

        # Generate embeddings for all chunks (process in batches of 8 to avoid memory issues)
        logger.info(f"About to start embedding generation for {len(chunks)} chunks...")
        logger.info(f"First chunk preview: {chunks[0][:100]}...")

        try:
            embeddings = embedding_service.generate_embeddings(chunks, batch_size=8)
            logger.info(f"Completed embedding generation - got {len(embeddings)} embeddings")
        except Exception as embed_error:
            logger.error(f"Failed to generate embeddings: {embed_error}", exc_info=True)
            raise

        # Store embeddings in database
        doc_uuid = UUID(document_id)
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            doc_embedding = DocumentEmbedding(
                document_id=doc_uuid,
                chunk_index=idx,
                chunk_text=chunk,
                embedding=embedding,
                embedding_model=embedding_service.model_name,
            )
            db.add(doc_embedding)

        # Update document status using raw SQL
        db.execute(
            sql_text("UPDATE documents SET processing_status = 'embedding_complete' WHERE id = :doc_id"),
            {"doc_id": document_id}
        )
        db.commit()

        logger.info(
            f"Generated {len(embeddings)} embeddings for document {document_id}"
        )

        return {
            "status": "success",
            "document_id": document_id,
            "embedding_count": len(embeddings),
            "chunk_count": len(chunks),
        }

    except Exception as e:
        logger.error(
            f"Error generating embeddings for document {document_id}: {e}", exc_info=True
        )

        # Update document with error status using raw SQL
        try:
            db.execute(
                sql_text("UPDATE documents SET processing_status = 'failed', processing_error = :error WHERE id = :doc_id"),
                {"error": f"Embedding generation failed: {str(e)}", "doc_id": document_id}
            )
            db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update error status: {db_error}")

        return {"status": "error", "document_id": document_id, "message": str(e)}

    finally:
        db.close()
