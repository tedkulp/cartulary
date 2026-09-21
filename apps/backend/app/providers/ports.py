"""The two model ports and the single model error type.

Every port instance is bound to one provider and one model, so services never see
provider or model names. Ports are structural: anything with the right methods fits.
"""
from dataclasses import dataclass
from typing import List, Literal, Optional, Protocol, Sequence

Role = Literal["system", "user", "assistant"]


class ModelError(Exception):
    """Any provider failure: unreachable host, missing SDK, timeout or bad response.

    Processing treats this as worth another attempt, because most of the class is
    transient. Raise `ModelConfigurationError` for the part that is not.
    """


class ModelConfigurationError(ModelError):
    """A provider failure this deployment is configured into: no key, no SDK, no support.

    Still a `ModelError`, so every caller that handles one handles this, but it will
    read exactly the same on the fourth attempt as on the first, so processing does not
    retry it and fails the Document at once with the operator's answer in it (ADR 0007).
    """


@dataclass(frozen=True)
class Message:
    """One chat message. Images are raw encoded bytes (e.g. PNG), never base64."""

    role: Role
    content: str
    images: Sequence[bytes] = ()


class ChatModel(Protocol):
    """Turns messages, optionally carrying images, into the whole reply as text."""

    @property
    def model_name(self) -> str:
        """Name of the model answering, used to tell one model's output from another's."""
        ...

    def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Return the model's reply. Raises ModelError on any provider failure."""
        ...


class Embedder(Protocol):
    """Turns texts into vectors of one fixed dimension."""

    @property
    def dimension(self) -> int:
        """Length of every vector this embedder returns."""
        ...

    @property
    def model_name(self) -> str:
        """Name of the model producing the vectors, recorded on each chunk."""
        ...

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Return one vector per text. Raises ModelError on any provider failure."""
        ...
