"""Builds each model role from settings. The only place that chooses providers.

Each builder is cached once per process. A disabled capability returns None.
"""
import logging
from functools import lru_cache
from typing import Optional

from app.config import settings
from app.providers.ollama import OllamaChatModel
from app.providers.ports import ChatModel

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = "http://localhost:11434"


def _ollama_chat_model(model: str) -> OllamaChatModel:
    return OllamaChatModel(
        host=settings.LLM_BASE_URL or DEFAULT_OLLAMA_HOST,
        model=model,
        timeout=settings.MODEL_TIMEOUT_SECONDS,
    )


@lru_cache(maxsize=None)
def get_vision_model() -> Optional[ChatModel]:
    """The chat model that reads raw text off page images (OCR pass 1). Ollama only for now."""
    if not settings.OCR_ENABLED:
        return None
    model = _ollama_chat_model(settings.VISION_OCR_MODEL)
    logger.info(f"Vision model: {model!r}")
    return model


@lru_cache(maxsize=None)
def get_formatter_model() -> Optional[ChatModel]:
    """The chat model that turns raw OCR text into markdown (OCR pass 2). Ollama only for now."""
    if not settings.OCR_ENABLED:
        return None
    model = _ollama_chat_model(settings.OCR_FORMATTER_MODEL)
    logger.info(f"Formatter model: {model!r}")
    return model
