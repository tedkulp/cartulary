"""Schema for the capabilities a deployment has turned on."""
from pydantic import BaseModel, Field


class CapabilitiesResponse(BaseModel):
    """Which optional capabilities this deployment can do.

    A capability reported false means the endpoints behind it answer 503 (ADR 0003),
    so a client should hide or disable the feature rather than offer one that fails.
    """

    ocr: bool = Field(description="Pages can be read by a vision model (OCR_ENABLED).")
    embeddings: bool = Field(
        description="Documents can be embedded for semantic search (EMBEDDING_ENABLED)."
    )
    chat: bool = Field(description="Documents can be asked questions (LLM_ENABLED).")
    metadata: bool = Field(
        description="Metadata can be extracted from documents (LLM_ENABLED)."
    )
