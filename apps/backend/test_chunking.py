#!/usr/bin/env python3
"""Test script to verify text chunking works correctly."""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.embedding_service import EmbeddingService

def test_chunking():
    """Test the chunk_text function with various inputs."""

    # Create a minimal embedding service (no provider needed for chunking)
    service = EmbeddingService(provider="openai", model_name="test", dimension=384)

    print("=" * 80)
    print("TEST 1: Simple short text (< chunk_size)")
    print("=" * 80)
    text1 = "This is a short test."
    print(f"Input text: '{text1}' (length: {len(text1)})")
    print(f"Chunk size: 500, overlap: 50")

    chunks1 = service.chunk_text(text1, chunk_size=500, chunk_overlap=50)
    print(f"Result: {len(chunks1)} chunks")
    for i, chunk in enumerate(chunks1):
        print(f"  Chunk {i+1}: '{chunk}' (length: {len(chunk)})")
    print()

    print("=" * 80)
    print("TEST 2: Medium text (~ 1000 chars)")
    print("=" * 80)
    text2 = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 20
    print(f"Input text length: {len(text2)} characters")
    print(f"Chunk size: 500, overlap: 50")

    chunks2 = service.chunk_text(text2, chunk_size=500, chunk_overlap=50)
    print(f"Result: {len(chunks2)} chunks")
    for i, chunk in enumerate(chunks2):
        print(f"  Chunk {i+1} length: {len(chunk)}")
        print(f"    First 50 chars: '{chunk[:50]}...'")
    print()

    print("=" * 80)
    print("TEST 3: Real document text (3531 chars - from actual failing document)")
    print("=" * 80)
    # Simulate the size of the failing document
    text3 = "This is a test document. " * 141  # ~3531 characters
    print(f"Input text length: {len(text3)} characters")
    print(f"Chunk size: 500, overlap: 50")

    print("\nCalling chunk_text...")
    try:
        chunks3 = service.chunk_text(text3, chunk_size=500, chunk_overlap=50)
        print(f"✓ Chunking completed successfully!")
        print(f"Result: {len(chunks3)} chunks")
        for i, chunk in enumerate(chunks3):
            print(f"  Chunk {i+1} length: {len(chunk)}")
    except Exception as e:
        print(f"✗ Chunking failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()

    print("=" * 80)
    print("TEST 4: Empty text")
    print("=" * 80)
    text4 = ""
    print(f"Input text: '{text4}' (length: {len(text4)})")

    chunks4 = service.chunk_text(text4, chunk_size=500, chunk_overlap=50)
    print(f"Result: {len(chunks4)} chunks")
    print()

    print("=" * 80)
    print("TEST 5: Edge case - exactly chunk_size length")
    print("=" * 80)
    text5 = "x" * 500
    print(f"Input text length: {len(text5)} characters")

    chunks5 = service.chunk_text(text5, chunk_size=500, chunk_overlap=50)
    print(f"Result: {len(chunks5)} chunks")
    for i, chunk in enumerate(chunks5):
        print(f"  Chunk {i+1} length: {len(chunk)}")
    print()

    print("=" * 80)
    print("TEST 6: Performance test with large text")
    print("=" * 80)
    text6 = "This is a large document for performance testing. " * 1000  # ~51,000 chars
    print(f"Input text length: {len(text6)} characters")

    import time
    start = time.time()
    chunks6 = service.chunk_text(text6, chunk_size=500, chunk_overlap=50)
    elapsed = time.time() - start

    print(f"✓ Chunking completed in {elapsed:.4f} seconds")
    print(f"Result: {len(chunks6)} chunks")
    print()

    print("=" * 80)
    print("ALL TESTS PASSED!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    success = test_chunking()
    sys.exit(0 if success else 1)
