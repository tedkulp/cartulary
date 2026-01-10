#!/usr/bin/env python3
"""Test if converting to plain string helps."""
import sys
import logging
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.document import Document
from app.services.embedding_service import EmbeddingService
from app.config import settings

document_id = "3c78c4c1-7820-479e-b9dd-3d77acd60ba7"
db: Session = SessionLocal()

try:
    logger.info("Getting document from database")
    doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
    logger.info(f"Got document with {len(doc.ocr_text)} characters")

    logger.info("Converting to plain string")
    plain_text = str(doc.ocr_text)  # Explicit conversion
    logger.info(f"Converted to string: {type(plain_text)}")

    logger.info("Creating embedding service")
    service = EmbeddingService(
        provider="openai",
        model_name="text-embedding-3-small",
        dimension=1536
    )

    logger.info("Chunking with PLAIN STRING")
    chunks = service.chunk_text(plain_text, chunk_size=500, chunk_overlap=50)
    logger.info(f"✓ SUCCESS! Got {len(chunks)} chunks")

finally:
    db.close()
