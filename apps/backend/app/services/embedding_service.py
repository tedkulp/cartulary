"""Embedding service for generating vector embeddings."""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using local models, OpenAI API, or Ollama."""

    def __init__(
        self,
        provider: str = "local",
        model_name: str = "all-MiniLM-L6-v2",
        api_key: Optional[str] = None,
        dimension: Optional[int] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize embedding service.

        Args:
            provider: Embedding provider ("local", "openai", or "ollama")
            model_name: Model name (all-MiniLM-L6-v2 for local, text-embedding-3-small for OpenAI, nomic-embed-text for Ollama)
            api_key: OpenAI API key (required if provider="openai")
            dimension: Embedding dimension (if not provided, will be auto-detected)
            base_url: Base URL for Ollama (default: http://localhost:11434)
        """
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url or "http://localhost:11434"
        self.model = None
        self._ollama_client = None

        # Set dimension (use provided or auto-detect)
        if dimension:
            self.dimension = dimension
        elif provider == "openai":
            if "text-embedding-3-small" in model_name:
                self.dimension = 1536
            elif "text-embedding-3-large" in model_name:
                self.dimension = 3072
            elif "text-embedding-ada-002" in model_name:
                self.dimension = 1536
            else:
                self.dimension = 1536  # Default for OpenAI
        elif provider == "ollama":
            # Common Ollama embedding models
            if "nomic-embed-text" in model_name:
                self.dimension = 768
            elif "mxbai-embed-large" in model_name:
                self.dimension = 1024
            elif "all-minilm" in model_name:
                self.dimension = 384
            else:
                self.dimension = 768  # Default for Ollama
        else:
            # Local sentence-transformers models
            if "mpnet" in model_name:
                self.dimension = 768
            elif "MiniLM" in model_name:
                self.dimension = 384
            else:
                self.dimension = 384  # Default

    def _load_model(self):
        """Lazy load the embedding model (local models only)."""
        if self.provider in ["openai", "ollama"]:
            # OpenAI and Ollama don't need a loaded model
            return

        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading local embedding model: {self.model_name}")
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

    def _initialize_ollama_client(self):
        """Lazy initialize Ollama client."""
        if self._ollama_client is None:
            try:
                import ollama
                self._ollama_client = ollama.Client(host=self.base_url)
                logger.info(f"Ollama embedding client initialized (host={self.base_url}, model={self.model_name})")
            except ImportError:
                logger.error("ollama package not installed. Install with: pip install ollama")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Ollama client: {e}")
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

        if self.provider == "openai":
            return self._generate_openai_embedding(text)
        elif self.provider == "ollama":
            return self._generate_ollama_embedding(text)
        else:
            return self._generate_local_embedding(text)

    def _generate_local_embedding(self, text: str) -> List[float]:
        """Generate embedding using local sentence-transformers model."""
        self._load_model()

        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate local embedding: {e}")
            raise

    def _generate_openai_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API."""
        try:
            from openai import OpenAI

            if not self.api_key:
                raise ValueError("OpenAI API key is required for OpenAI embeddings")

            client = OpenAI(api_key=self.api_key)
            response = client.embeddings.create(input=text, model=self.model_name)
            return response.data[0].embedding
        except ImportError:
            logger.error("openai package not installed. Install with: pip install openai")
            raise
        except Exception as e:
            logger.error(f"Failed to generate OpenAI embedding: {e}")
            raise

    def _generate_ollama_embedding(self, text: str) -> List[float]:
        """Generate embedding using Ollama."""
        self._initialize_ollama_client()

        try:
            response = self._ollama_client.embeddings(
                model=self.model_name,
                prompt=text
            )
            return response["embedding"]
        except Exception as e:
            logger.error(f"Failed to generate Ollama embedding: {e}")
            raise

    def generate_embeddings(self, texts: List[str], batch_size: int = 8) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing).

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process at once (smaller = less memory for local)

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        if self.provider == "openai":
            return self._generate_openai_embeddings(texts, batch_size)
        elif self.provider == "ollama":
            return self._generate_ollama_embeddings(texts, batch_size)
        else:
            return self._generate_local_embeddings(texts, batch_size)

    def _generate_local_embeddings(self, texts: List[str], batch_size: int) -> List[List[float]]:
        """Generate embeddings using local sentence-transformers model."""
        self._load_model()

        try:
            all_embeddings = []

            # Process in smaller batches to avoid memory issues
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                logger.info(f"Processing local embedding batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1} ({len(batch)} chunks)")

                batch_embeddings = self.model.encode(
                    batch,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                    batch_size=batch_size
                )
                all_embeddings.extend(batch_embeddings.tolist())

            return all_embeddings
        except Exception as e:
            logger.error(f"Failed to generate local batch embeddings: {e}")
            raise

    def _generate_openai_embeddings(self, texts: List[str], batch_size: int) -> List[List[float]]:
        """Generate embeddings using OpenAI API (supports up to 2048 texts per request)."""
        logger.info(f"_generate_openai_embeddings called with {len(texts)} texts, batch_size={batch_size}")

        try:
            logger.info("Importing OpenAI package...")
            from openai import OpenAI
            logger.info("OpenAI package imported successfully")

            if not self.api_key:
                raise ValueError("OpenAI API key is required for OpenAI embeddings")

            logger.info(f"Creating OpenAI client (API key length: {len(self.api_key) if self.api_key else 0})")
            client = OpenAI(api_key=self.api_key)
            logger.info("OpenAI client created successfully")

            all_embeddings = []

            # OpenAI supports large batches (up to 2048), but we'll use smaller batches
            # to avoid rate limits and allow for retries
            openai_batch_size = min(batch_size * 10, 100)  # Process up to 100 at a time
            logger.info(f"Using OpenAI batch size: {openai_batch_size}")

            for i in range(0, len(texts), openai_batch_size):
                batch = texts[i:i + openai_batch_size]
                batch_num = i//openai_batch_size + 1
                total_batches = (len(texts)-1)//openai_batch_size + 1

                logger.info(f"Processing OpenAI embedding batch {batch_num}/{total_batches} ({len(batch)} chunks)")
                logger.info(f"First text in batch preview: {batch[0][:50]}...")

                try:
                    logger.info(f"Making OpenAI API call for batch {batch_num}...")
                    response = client.embeddings.create(input=batch, model=self.model_name)
                    logger.info(f"OpenAI API call successful for batch {batch_num}")

                    batch_embeddings = [item.embedding for item in response.data]
                    logger.info(f"Extracted {len(batch_embeddings)} embeddings from response")
                    all_embeddings.extend(batch_embeddings)
                    logger.info(f"Total embeddings so far: {len(all_embeddings)}")
                except Exception as batch_error:
                    logger.error(f"Error processing batch {batch_num}: {batch_error}", exc_info=True)
                    raise

            logger.info(f"Completed all batches - returning {len(all_embeddings)} embeddings")
            return all_embeddings

        except ImportError as import_error:
            logger.error(f"openai package not installed: {import_error}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to generate OpenAI batch embeddings: {e}", exc_info=True)
            raise

    def _generate_ollama_embeddings(self, texts: List[str], batch_size: int) -> List[List[float]]:
        """Generate embeddings using Ollama (processes one at a time)."""
        self._initialize_ollama_client()

        try:
            all_embeddings = []

            # Ollama processes embeddings one at a time
            for i, text in enumerate(texts):
                if i % 10 == 0:  # Log progress every 10 texts
                    logger.info(f"Processing Ollama embedding {i+1}/{len(texts)}")

                response = self._ollama_client.embeddings(
                    model=self.model_name,
                    prompt=text
                )
                all_embeddings.append(response["embedding"])

            logger.info(f"Completed Ollama embeddings - returning {len(all_embeddings)} embeddings")
            return all_embeddings

        except Exception as e:
            logger.error(f"Failed to generate Ollama batch embeddings: {e}", exc_info=True)
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
        logger.info(f"[CHUNK_TEXT] Entered function with text length: {len(text) if text else 0}, chunk_size: {chunk_size}, overlap: {chunk_overlap}")

        if not text or len(text) <= chunk_size:
            logger.info(f"[CHUNK_TEXT] Text is short, returning single chunk or empty list")
            return [text] if text else []

        logger.info(f"[CHUNK_TEXT] Starting chunking loop...")
        chunks = []
        start = 0

        while start < len(text):
            logger.info(f"[CHUNK_TEXT] Loop iteration: start={start}, len(text)={len(text)}")
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
