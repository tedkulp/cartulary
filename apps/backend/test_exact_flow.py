#!/usr/bin/env python3
"""Test the exact flow of the Celery task."""
import sys
import logging
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("="*80)
logger.info("Starting exact flow test")
logger.info("="*80)

logger.info("Step 1: Import all modules")
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.document import Document, DocumentEmbedding
from app.services.embedding_service import EmbeddingService
from app.config import settings
logger.info("✓ All imports successful\n")

document_id = "3c78c4c1-7820-479e-b9dd-3d77acd60ba7"

logger.info("Step 2: Create database session")
db: Session = SessionLocal()
logger.info("✓ Session created\n")

try:
    logger.info("Step 3: Get document from database")
    doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
    logger.info(f"✓ Got document: {doc.title}\n")

    logger.info("Step 4: Check OCR text")
    logger.info(f"OCR text length: {len(doc.ocr_text) if doc.ocr_text else 0}")
    logger.info(f"OCR text type: {type(doc.ocr_text)}")
    logger.info(f"OCR text preview: {doc.ocr_text[:100] if doc.ocr_text else 'None'}\n")

    logger.info("Step 5: Delete existing embeddings")
    db.query(DocumentEmbedding).filter(
        DocumentEmbedding.document_id == doc.id
    ).delete()
    db.commit()
    logger.info("✓ Deleted embeddings\n")

    logger.info("Step 6: Initialize embedding service")
    embedding_service = EmbeddingService(
        provider=settings.EMBEDDING_PROVIDER,
        model_name=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY if settings.EMBEDDING_PROVIDER == "openai" else None,
        dimension=settings.EMBEDDING_DIMENSION,
    )
    logger.info(f"✓ Embedding service created\n")

    logger.info("Step 7: Chunk the text")
    logger.info(f"About to call chunk_text with {len(doc.ocr_text)} characters")
    chunks = embedding_service.chunk_text(
        doc.ocr_text,
        chunk_size=settings.EMBEDDING_CHUNK_SIZE,
        chunk_overlap=settings.EMBEDDING_CHUNK_OVERLAP
    )
    logger.info(f"✓ Got {len(chunks)} chunks\n")

    logger.info("="*80)
    logger.info("SUCCESS! All steps completed")
    logger.info("="*80)

finally:
    logger.info("Closing database session")
    db.close()
