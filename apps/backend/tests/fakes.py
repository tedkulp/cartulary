"""Test doubles for the model ports. They satisfy the ports structurally."""
import hashlib
from typing import List, Optional, Sequence, Union

from app.providers import Message, ModelError


class ScriptedChatModel:
    """Chat model that returns queued replies and records every message list it gets.

    A queued reply that is an exception is raised instead (wrapped in ModelError
    unless it already is one). Running out of replies fails the test loudly.
    """

    def __init__(self, *replies: Union[str, Exception]) -> None:
        self._replies = list(replies)
        self.calls: List[List[Message]] = []

    def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        self.calls.append(list(messages))
        if not self._replies:
            raise AssertionError("ScriptedChatModel received more calls than scripted replies")
        reply = self._replies.pop(0)
        if isinstance(reply, ModelError):
            raise reply
        if isinstance(reply, Exception):
            raise ModelError(str(reply)) from reply
        return reply


class FakeEmbedder:
    """Embedder returning deterministic vectors derived from each text's hash."""

    def __init__(self, dimension: int = 8, model_name: str = "fake-embedder") -> None:
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> List[float]:
        values: List[float] = []
        counter = 0
        while len(values) < self._dimension:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend(byte / 255.0 for byte in digest)
            counter += 1
        return values[: self._dimension]
