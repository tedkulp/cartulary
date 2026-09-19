"""Gemini adapter for the chat model port, on the `google-generativeai` SDK."""
import logging
from typing import Any, Dict, List, Optional, Sequence

from app.providers.ports import Message, ModelError

logger = logging.getLogger(__name__)


class GeminiChatModel:
    """Chat model served by Gemini, bound to one model. Text only for now (#8).

    System messages become Gemini's system instruction; assistant turns become "model" turns.
    """

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
        self._genai: Any = None

    @property
    def model_name(self) -> str:
        return self.model

    def __repr__(self) -> str:
        return f"GeminiChatModel(model={self.model!r})"

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

        system_texts = [m.content for m in messages if m.role == "system"]
        contents: List[Dict[str, Any]] = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [m.content]}
            for m in messages
            if m.role != "system"
        ]

        generation_config: Dict[str, Any] = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_tokens is not None:
            generation_config["max_output_tokens"] = max_tokens

        try:
            model = self._get_genai().GenerativeModel(
                self.model,
                system_instruction="\n\n".join(system_texts) if system_texts else None,
            )
            response = model.generate_content(
                contents,
                generation_config=generation_config or None,
                request_options={"timeout": self.timeout},
            )
            # Raises ValueError when the reply has no text, e.g. when it was blocked.
            return response.text
        except ModelError:
            raise
        except Exception as e:
            # The provider boundary: anything the SDK or transport raises is a model failure.
            raise ModelError(f"Gemini chat failed ({self!r}): {type(e).__name__}: {e}") from e

    def _get_genai(self) -> Any:
        if self._genai is None:
            if not self.api_key:
                raise ModelError("GEMINI_API_KEY is required for Gemini chat")
            try:
                import google.generativeai as genai
            except ImportError as e:
                raise ModelError(
                    "Google Generative AI library not installed. "
                    "Install with: pip install google-generativeai"
                ) from e
            # The SDK's configuration is process-wide, so the last Gemini model configured
            # wins. REST rather than gRPC, so a base URL can point it at any HTTP endpoint.
            genai.configure(
                api_key=self.api_key,
                transport="rest",
                client_options={"api_endpoint": self.base_url} if self.base_url else None,
            )
            self._genai = genai
        return self._genai
