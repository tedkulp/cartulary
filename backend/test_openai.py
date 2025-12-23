#!/usr/bin/env python3
"""Test script to verify OpenAI embeddings work outside of Celery."""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings

def test_openai_connection():
    """Test OpenAI API connection and embedding generation."""
    print(f"Testing OpenAI embeddings...")
    print(f"Provider: {settings.EMBEDDING_PROVIDER}")
    print(f"Model: {settings.EMBEDDING_MODEL}")
    print(f"Dimension: {settings.EMBEDDING_DIMENSION}")
    print(f"API Key length: {len(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else 0}")
    print(f"API Key prefix: {settings.OPENAI_API_KEY[:20]}..." if settings.OPENAI_API_KEY else "None")
    print()

    try:
        print("Importing OpenAI...")
        from openai import OpenAI
        print("✓ OpenAI package imported successfully")
        print()

        print("Creating OpenAI client...")
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        print("✓ OpenAI client created successfully")
        print()

        print("Testing embedding generation with simple text...")
        test_text = "This is a test document for embedding generation."

        print(f"Generating embedding for: '{test_text}'")
        response = client.embeddings.create(
            input=[test_text],
            model=settings.EMBEDDING_MODEL
        )
        print("✓ OpenAI API call successful")
        print()

        embedding = response.data[0].embedding
        print(f"✓ Received embedding with {len(embedding)} dimensions")
        print(f"First 5 values: {embedding[:5]}")
        print()

        print("SUCCESS! OpenAI embeddings are working correctly.")
        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_openai_connection()
    sys.exit(0 if success else 1)
