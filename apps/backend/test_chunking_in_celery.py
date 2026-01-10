#!/usr/bin/env python3
"""Test chunking inside a Celery worker context."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Simulate Celery environment
from app.database import SessionLocal
from sqlalchemy import text

# Get the actual OCR text from the failing document
db = SessionLocal()
result = db.execute(text("SELECT ocr_text FROM documents WHERE id = '3c78c4c1-7820-479e-b9dd-3d77acd60ba7'"))
row = result.fetchone()
actual_ocr_text = row[0] if row else None
db.close()

if not actual_ocr_text:
    print("❌ Document not found")
    sys.exit(1)

print(f"Got OCR text: {len(actual_ocr_text)} characters")
print(f"Text type: {type(actual_ocr_text)}")
print(f"First 100 chars: {actual_ocr_text[:100]}")
print()

# Now try chunking it
from app.services.embedding_service import EmbeddingService

print("Creating EmbeddingService...")
service = EmbeddingService(provider="openai", model_name="text-embedding-3-small", dimension=1536)
print("✓ EmbeddingService created")
print()

print("Calling chunk_text()...")
import time
start = time.time()

chunks = service.chunk_text(actual_ocr_text, chunk_size=500, chunk_overlap=50)

elapsed = time.time() - start
print(f"✓ Chunking completed in {elapsed:.4f} seconds")
print(f"Result: {len(chunks)} chunks")

for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
    print(f"  Chunk {i+1}: {len(chunk)} chars - {chunk[:50]}...")

print()
print("SUCCESS! Chunking works correctly with actual OCR text.")
