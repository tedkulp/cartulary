"""OpenAI adapter for the embedder port."""
import logging
from typing import Any, List, Optional, Sequence

from app.providers.ports import ModelError

logger = logging.getLogger(__name__)

# OpenAI accepts up to 2048 inputs per request; smaller batches keep each request quick.
EMBEDDING_BATCH_SIZE = 100


class OpenAIEmbedder:
    """Embedder served by OpenAI, bound to one model. Batches up to 100 texts per request."""

    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        dimension: int,
        timeout: float,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = base_url
        self._dimension = dimension
        self._client: Any = None

    def __repr__(self) -> str:
        return f"OpenAIEmbedder(model={self.model!r})"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self.model

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Return one vector per text. Raises ModelError on any provider failure."""
        if not texts:
            return []
        vectors: List[List[float]] = []
        try:
            client = self._get_client()
            total_batches = (len(texts) - 1) // EMBEDDING_BATCH_SIZE + 1
            for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
                batch = list(texts[start : start + EMBEDDING_BATCH_SIZE])
                logger.info(
                    f"OpenAI embedding batch {start // EMBEDDING_BATCH_SIZE + 1}/{total_batches} "
                    f"({len(batch)} texts, {self!r})"
                )
                response = client.embeddings.create(input=batch, model=self.model)
                vectors.extend(item.embedding for item in response.data)
        except ModelError:
            raise
        except Exception as e:
            # The provider boundary: anything the SDK or transport raises is a model failure.
            raise ModelError(f"OpenAI embedding failed ({self!r}): {type(e).__name__}: {e}") from e
        return vectors

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise ModelError("OPENAI_API_KEY is required for OpenAI embeddings")
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ModelError(
                    "OpenAI library not installed. Install with: pip install openai"
                ) from e
            # No retries here: the Celery tasks already retry failed work.
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=0,
            )
        return self._client
