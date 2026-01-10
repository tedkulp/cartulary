#!/usr/bin/env python3
"""Test if closing DB session before chunking helps."""
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

document_id = "3c78c4c1-7820-479e-b9dd-3d77acd60ba7"

logger.info("Creating database session")
db: Session = SessionLocal()

logger.info("Getting document from database")
doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
ocr_text_copy = str(doc.ocr_text)  # Make a copy
logger.info(f"Got text: {len(ocr_text_copy)} characters")

logger.info("CLOSING DATABASE SESSION BEFORE CHUNKING")
db.close()
logger.info("✓ Database session closed")

logger.info("Creating embedding service")
service = EmbeddingService(provider="openai", model_name="test", dimension=384)
logger.info("✓ Service created")

logger.info("Chunking (DB session is CLOSED)")
chunks = service.chunk_text(ocr_text_copy, chunk_size=500, chunk_overlap=50)
logger.info(f"✓ SUCCESS! Got {len(chunks)} chunks")
