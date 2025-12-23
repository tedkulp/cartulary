#!/usr/bin/env python3
"""
Helper script to update the embedding dimension when changing providers.

Usage:
    python scripts/update_embedding_dimension.py 384  # For local models
    python scripts/update_embedding_dimension.py 1536 # For OpenAI
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine
from sqlalchemy import text


def update_dimension(new_dimension: int):
    """Update the vector dimension in the database."""
    print(f"Updating embedding dimension to {new_dimension}...")

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        try:
            # Delete existing embeddings
            print("Deleting existing embeddings...")
            result = conn.execute(text("DELETE FROM document_embeddings"))
            print(f"Deleted {result.rowcount} embeddings")

            # Drop the column
            print("Dropping embedding column...")
            conn.execute(text("ALTER TABLE document_embeddings DROP COLUMN embedding"))

            # Add it back with new dimension
            print(f"Adding embedding column with dimension {new_dimension}...")
            conn.execute(
                text(f"ALTER TABLE document_embeddings ADD COLUMN embedding vector({new_dimension})")
            )

            # Commit transaction
            trans.commit()
            print(f"✓ Successfully updated dimension to {new_dimension}")
            print("\nNOTE: You need to regenerate embeddings for all documents.")

        except Exception as e:
            trans.rollback()
            print(f"✗ Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/update_embedding_dimension.py <dimension>")
        print("Examples:")
        print("  python scripts/update_embedding_dimension.py 384   # For local models")
        print("  python scripts/update_embedding_dimension.py 1536  # For OpenAI")
        sys.exit(1)

    try:
        dimension = int(sys.argv[1])
        if dimension not in [384, 768, 1536, 3072]:
            print(f"Warning: Unusual dimension {dimension}")
            confirm = input("Continue? (y/n): ")
            if confirm.lower() != 'y':
                sys.exit(0)

        update_dimension(dimension)

    except ValueError:
        print("Error: Dimension must be an integer")
        sys.exit(1)
