"""Embedding service for generating vector embeddings."""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding service.

        Args:
            model_name: Name of the sentence-transformers model to use
                       Default: all-MiniLM-L6-v2 (384 dimensions, fast and efficient)
        """
        self.model_name = model_name
        self.model = None
        self.dimension = 384  # Default for all-MiniLM-L6-v2

        # Set dimension based on model
        if "mpnet" in model_name:
            self.dimension = 768
        elif "MiniLM" in model_name:
            self.dimension = 384

    def _load_model(self):
        """Lazy load the embedding model."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                logger.info(f"Embedding model loaded successfully")
            except ImportError:
                logger.error(
                    "sentence-transformers not installed. Install with: pip install sentence-transformers"
                )
                raise
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dimension

        self._load_model()

        try:
            # Generate embedding
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        self._load_model()

        try:
            # Batch encode for efficiency
            embeddings = self.model.encode(
                texts, convert_to_numpy=True, show_progress_bar=len(texts) > 10
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    def chunk_text(
        self, text: str, chunk_size: int = 500, chunk_overlap: int = 50
    ) -> List[str]:
        """
        Split text into overlapping chunks for embedding.

        Args:
            text: Text to chunk
            chunk_size: Maximum number of characters per chunk
            chunk_overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks
        """
        if not text or len(text) <= chunk_size:
            return [text] if text else []

        chunks = []
        start = 0

        while start < len(text):
            # Find end of chunk
            end = start + chunk_size

            # If not at end, try to break at sentence or word boundary
            if end < len(text):
                # Look for sentence boundary (. ! ?)
                for punct in [". ", "! ", "? ", "\n\n"]:
                    last_punct = text.rfind(punct, start, end)
                    if last_punct > start:
                        end = last_punct + len(punct)
                        break
                else:
                    # No sentence boundary, try word boundary
                    last_space = text.rfind(" ", start, end)
                    if last_space > start:
                        end = last_space

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - chunk_overlap if end < len(text) else len(text)

        return chunks
