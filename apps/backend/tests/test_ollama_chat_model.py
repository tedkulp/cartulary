"""Tests for the Ollama chat model adapter.

The offline tests use real local sockets. The contract tests talk to a real Ollama and
only run with `pytest --live`.
"""
import socket
from typing import Iterator

import fitz
import pytest

from app.config import settings
from app.providers import Message, ModelError
from app.providers.factory import DEFAULT_OLLAMA_HOST
from app.providers.ollama import OllamaChatModel


@pytest.fixture
def unused_port() -> int:
    """A local port with nothing listening on it."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def silent_server() -> Iterator[str]:
    """A local server that accepts connections but never replies."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"


class TestOllamaChatModelFailures:
    """Every provider failure surfaces as ModelError."""

    def test_unreachable_host_raises_model_error(self, unused_port):
        model = OllamaChatModel(host=f"http://127.0.0.1:{unused_port}", model="any", timeout=5)

        with pytest.raises(ModelError):
            model.chat([Message(role="user", content="hello")])

    def test_timeout_raises_model_error(self, silent_server):
        model = OllamaChatModel(host=silent_server, model="any", timeout=0.2)

        with pytest.raises(ModelError):
            model.chat([Message(role="user", content="hello")])


@pytest.mark.live
class TestOllamaChatModelContract:
    """Contract tests against the Ollama at LLM_BASE_URL, using the OCR model settings."""

    @pytest.fixture
    def host(self) -> str:
        return settings.LLM_BASE_URL or DEFAULT_OLLAMA_HOST

    def test_chat_returns_text(self, host):
        model = OllamaChatModel(host=host, model=settings.OCR_FORMATTER_MODEL, timeout=120)

        reply = model.chat(
            [
                Message(role="system", content="Reply with exactly one word."),
                Message(role="user", content="Say hello."),
            ],
            temperature=0.0,
        )

        assert isinstance(reply, str)
        assert reply.strip()

    def test_chat_reads_text_from_image(self, host):
        doc = fitz.open()
        page = doc.new_page(width=400, height=120)
        page.insert_text((20, 70), "CARTULARY", fontsize=48)
        image = page.get_pixmap().tobytes("png")
        model = OllamaChatModel(host=host, model=settings.VISION_OCR_MODEL, timeout=300)

        reply = model.chat(
            [Message(role="user", content="What word is in this image?", images=[image])]
        )

        assert "cartulary" in reply.lower()

    def test_missing_model_raises_model_error(self, host):
        model = OllamaChatModel(host=host, model="cartulary-no-such-model", timeout=30)

        with pytest.raises(ModelError):
            model.chat([Message(role="user", content="hello")])
