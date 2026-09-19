"""OpenAI adapters for the chat model and embedder ports."""
import logging
from typing import Any, Dict, List, Optional, Sequence

from app.providers.ports import Message, ModelError

logger = logging.getLogger(__name__)

# OpenAI accepts up to 2048 inputs per request; smaller batches keep each request quick.
EMBEDDING_BATCH_SIZE = 100


def _new_client(api_key: Optional[str], base_url: Optional[str], timeout: float, purpose: str) -> Any:
    if not api_key:
        raise ModelError(f"OPENAI_API_KEY is required for OpenAI {purpose}")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ModelError("OpenAI library not installed. Install with: pip install openai") from e
    # No retries here: the Celery tasks already retry failed work.
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)


class OpenAIChatModel:
    """Chat model served by OpenAI, bound to one model. Text only for now (#8)."""

    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        timeout: float,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = base_url
        self._client: Any = None

    def __repr__(self) -> str:
        return f"OpenAIChatModel(model={self.model!r})"

    def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Return the model's whole reply. Raises ModelError on any provider failure."""
        if any(message.images for message in messages):
            raise ModelError(f"{self!r} does not accept images yet")

        options: Dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["max_tokens"] = max_tokens

        try:
            response = self._get_client().chat.completions.create(
                model=self.model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                **options,
            )
            return response.choices[0].message.content or ""
        except ModelError:
            raise
        except Exception as e:
            # The provider boundary: anything the SDK or transport raises is a model failure.
            raise ModelError(f"OpenAI chat failed ({self!r}): {type(e).__name__}: {e}") from e

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = _new_client(self.api_key, self.base_url, self.timeout, "chat")
        return self._client


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
            self._client = _new_client(self.api_key, self.base_url, self.timeout, "embeddings")
        return self._client
