"""Ollama adapters for the chat model and embedder ports."""
import logging
from typing import Any, Dict, List, Optional, Sequence

from app.providers.ports import Message, ModelError

logger = logging.getLogger(__name__)


def _new_client(host: str, timeout: float) -> Any:
    try:
        import ollama
    except ImportError as e:
        raise ModelError("Ollama library not installed. Install with: pip install ollama") from e
    # Extra kwargs are passed through to the underlying httpx client.
    return ollama.Client(host=host, timeout=timeout)


class OllamaChatModel:
    """Chat model served by Ollama, bound to one host and one model. Supports images."""

    def __init__(self, host: str, model: str, timeout: float) -> None:
        self.host = host
        self.model = model
        self.timeout = timeout
        self._client: Any = None

    @property
    def model_name(self) -> str:
        return self.model

    def __repr__(self) -> str:
        return f"OllamaChatModel(model={self.model!r}, host={self.host!r})"

    def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Return the model's whole reply. Raises ModelError on any provider failure."""
        options: Dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        ollama_messages = [self._to_ollama(message) for message in messages]

        try:
            # Stream so the timeout bounds each silence, not the whole generation.
            chunks = self._get_client().chat(
                model=self.model,
                messages=ollama_messages,
                options=options or None,
                stream=True,
            )
            return "".join(chunk["message"]["content"] or "" for chunk in chunks)
        except ModelError:
            raise
        except Exception as e:
            # The provider boundary: anything the SDK or transport raises is a model failure.
            raise ModelError(f"Ollama chat failed ({self!r}): {type(e).__name__}: {e}") from e

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = _new_client(self.host, self.timeout)
        return self._client

    @staticmethod
    def _to_ollama(message: Message) -> Dict[str, Any]:
        converted: Dict[str, Any] = {"role": message.role, "content": message.content}
        if message.images:
            # The SDK base64-encodes raw bytes itself.
            converted["images"] = list(message.images)
        return converted


class OllamaEmbedder:
    """Embedder served by Ollama, bound to one host and one model. One request per text."""

    def __init__(self, host: str, model: str, dimension: int, timeout: float) -> None:
        self.host = host
        self.model = model
        self.timeout = timeout
        self._dimension = dimension
        self._client: Any = None

    def __repr__(self) -> str:
        return f"OllamaEmbedder(model={self.model!r}, host={self.host!r})"

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
            for i, text in enumerate(texts):
                if i % 10 == 0:
                    logger.info(f"Ollama embedding {i + 1}/{len(texts)} ({self!r})")
                response = client.embeddings(model=self.model, prompt=text)
                vectors.append(list(response["embedding"]))
        except ModelError:
            raise
        except Exception as e:
            # The provider boundary: anything the SDK or transport raises is a model failure.
            raise ModelError(f"Ollama embedding failed ({self!r}): {type(e).__name__}: {e}") from e
        return vectors

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = _new_client(self.host, self.timeout)
        return self._client
