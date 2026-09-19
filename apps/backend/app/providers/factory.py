"""Builds each model role from settings. The only place that chooses providers.

Each builder is cached once per process. A disabled capability returns None.
"""
import logging
from functools import lru_cache
from typing import Optional

from app.config import settings
from app.providers.gemini import GeminiChatModel
from app.providers.local import LocalEmbedder
from app.providers.ollama import OllamaChatModel, OllamaEmbedder
from app.providers.openai import OpenAIChatModel, OpenAIEmbedder
from app.providers.ports import ChatModel, Embedder

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


@lru_cache(maxsize=None)
def get_assistant_model() -> Optional[ChatModel]:
    """The chat model for metadata extraction and RAG answers, from the LLM_* settings."""
    if not settings.LLM_ENABLED:
        return None
    provider = settings.LLM_PROVIDER
    model: ChatModel
    if provider == "ollama":
        model = _ollama_chat_model(settings.LLM_MODEL)
    elif provider == "openai":
        model = OpenAIChatModel(
            api_key=settings.OPENAI_API_KEY,
            model=settings.LLM_MODEL,
            timeout=settings.MODEL_TIMEOUT_SECONDS,
        )
    elif provider == "gemini":
        model = GeminiChatModel(
            api_key=settings.GEMINI_API_KEY,
            model=settings.LLM_MODEL,
            timeout=settings.MODEL_TIMEOUT_SECONDS,
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER {provider!r}: expected ollama, openai or gemini")
    logger.info(f"Assistant model: {model!r}")
    return model


@lru_cache(maxsize=None)
def get_embedder() -> Optional[Embedder]:
    """The embedder for document chunks and search queries, from the EMBEDDING_* settings."""
    if not settings.EMBEDDING_ENABLED:
        return None
    provider = settings.EMBEDDING_PROVIDER
    model = settings.EMBEDDING_MODEL
    dimension = settings.EMBEDDING_DIMENSION
    embedder: Embedder
    if provider == "ollama":
        embedder = OllamaEmbedder(
            host=settings.LLM_BASE_URL or DEFAULT_OLLAMA_HOST,
            model=model,
            dimension=dimension,
            timeout=settings.MODEL_TIMEOUT_SECONDS,
        )
    elif provider == "openai":
        embedder = OpenAIEmbedder(
            api_key=settings.OPENAI_API_KEY,
            model=model,
            dimension=dimension,
            timeout=settings.MODEL_TIMEOUT_SECONDS,
        )
    elif provider == "local":
        embedder = LocalEmbedder(model=model, dimension=dimension)
    else:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER {provider!r}: expected ollama, openai or local"
        )
    logger.info(f"Embedder: {embedder!r} (dimension {dimension})")
    return embedder
