"""Startup validation and initialization."""
import logging
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.database import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)


def validate_embedding_dimension():
    """
    Validate that the database vector dimension matches the configured dimension.

    Raises:
        ValueError: If dimensions don't match
        RuntimeError: If unable to check dimension
    """
    if not settings.EMBEDDING_ENABLED:
        logger.info("Embeddings disabled, skipping dimension validation")
        return

    try:
        db = SessionLocal()
        try:
            # Query the vector column type to get its dimension
            result = db.execute(text("""
                SELECT atttypmod
                FROM pg_attribute
                WHERE attrelid = 'document_embeddings'::regclass
                AND attname = 'embedding'
            """))
            row = result.fetchone()

            if not row:
                raise RuntimeError(
                    "Could not find embedding column in document_embeddings table. "
                    "Run database migrations first."
                )

            # For pgvector, atttypmod directly stores the dimension
            db_dimension = row[0] if row[0] > 0 else None

            if db_dimension is None:
                raise RuntimeError(
                    "Could not determine vector dimension from database. "
                    "The embedding column may not be properly configured."
                )

            configured_dimension = settings.EMBEDDING_DIMENSION

            if db_dimension != configured_dimension:
                raise ValueError(
                    f"DIMENSION MISMATCH!\n"
                    f"  Database vector dimension: {db_dimension}\n"
                    f"  Configured dimension (EMBEDDING_DIMENSION): {configured_dimension}\n"
                    f"  Embedding provider: {settings.EMBEDDING_PROVIDER}\n"
                    f"  Embedding model: {settings.EMBEDDING_MODEL}\n\n"
                    f"This mismatch will cause embedding operations to fail.\n\n"
                    f"To fix this:\n"
                    f"  1. If you changed providers, update the database:\n"
                    f"     docker exec cartulary-backend python scripts/update_embedding_dimension.py {configured_dimension}\n"
                    f"  2. Or update your .env file to match the database dimension:\n"
                    f"     EMBEDDING_DIMENSION={db_dimension}\n"
                    f"  3. Restart the application\n"
                    f"  4. Regenerate all embeddings with the correct provider/dimension"
                )

            logger.info(
                f"✓ Embedding dimension validation passed: "
                f"{db_dimension} dimensions ({settings.EMBEDDING_PROVIDER}/{settings.EMBEDDING_MODEL})"
            )

        finally:
            db.close()

    except OperationalError as e:
        logger.warning(f"Could not validate embedding dimension (database not ready?): {e}")
        # Don't fail startup if database isn't ready yet
    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating embedding dimension: {e}")
        raise RuntimeError(f"Failed to validate embedding configuration: {e}")


def startup_checks():
    """Run all startup validation checks."""
    logger.info("Running startup validation checks...")

    try:
        validate_embedding_dimension()
        logger.info("✓ All startup checks passed")
    except ValueError as e:
        logger.error(f"✗ Startup validation failed:\n{e}")
        raise
    except RuntimeError as e:
        logger.error(f"✗ Startup check error: {e}")
        raise
