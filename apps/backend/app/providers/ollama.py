"""Ollama adapter for the chat model port."""
import logging
from typing import Any, Dict, Optional, Sequence

from app.providers.ports import Message, ModelError

logger = logging.getLogger(__name__)


class OllamaChatModel:
    """Chat model served by Ollama, bound to one host and one model. Supports images."""

    def __init__(self, host: str, model: str, timeout: float) -> None:
        self.host = host
        self.model = model
        self.timeout = timeout
        self._client: Any = None

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
            try:
                import ollama
            except ImportError as e:
                raise ModelError(
                    "Ollama library not installed. Install with: pip install ollama"
                ) from e
            # Extra kwargs are passed through to the underlying httpx client.
            self._client = ollama.Client(host=self.host, timeout=self.timeout)
        return self._client

    @staticmethod
    def _to_ollama(message: Message) -> Dict[str, Any]:
        converted: Dict[str, Any] = {"role": message.role, "content": message.content}
        if message.images:
            # The SDK base64-encodes raw bytes itself.
            converted["images"] = list(message.images)
        return converted
