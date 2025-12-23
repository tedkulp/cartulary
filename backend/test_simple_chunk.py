#!/usr/bin/env python3
"""Minimal test of chunking."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("Test 1: Import embedding service")
from app.services.embedding_service import EmbeddingService
print("✓ Import successful\n")

print("Test 2: Create service instance")
service = EmbeddingService(provider="openai", model_name="text-embedding-3-small", dimension=1536)
print("✓ Service created\n")

print("Test 3: Chunk simple text")
text = "Test " * 700  # 3500 characters
print(f"Text length: {len(text)}")
chunks = service.chunk_text(text, chunk_size=500, chunk_overlap=50)
print(f"✓ Got {len(chunks)} chunks\n")

print("SUCCESS!")
