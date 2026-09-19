"""Tests for the Ollama, OpenAI and local sentence-transformers embedder adapters.

The offline tests use real local sockets. The contract tests talk to real providers and
only run with `pytest --live`.
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List

import pytest

from app.config import settings
from app.providers import ModelError
from app.providers.factory import DEFAULT_OLLAMA_HOST
from app.providers.local import LocalEmbedder
from app.providers.ollama import OllamaEmbedder
from app.providers.openai import OpenAIEmbedder


class FakeOpenAIEmbeddings:
    """A local OpenAI-compatible /embeddings endpoint that records each request's inputs."""

    def __init__(self) -> None:
        self.requests: List[List[str]] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                inputs = body["input"]
                fake.requests.append(inputs)
                payload = {
                    "object": "list",
                    "model": body["model"],
                    "data": [
                        {"object": "embedding", "index": i, "embedding": [float(len(text)), 1.0]}
                        for i, text in enumerate(inputs)
                    ],
                    "usage": {"prompt_tokens": 0, "total_tokens": 0},
                }
                encoded = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}/v1"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeOpenAIEmbeddings":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()


class TestEmbedderIdentity:
    """Each embedder exposes the dimension and model name it was built with."""

    @pytest.mark.parametrize(
        "embedder",
        [
            OllamaEmbedder(host="http://ollama.test", model="m", dimension=768, timeout=1),
            OpenAIEmbedder(api_key="k", model="m", dimension=768, timeout=1),
            LocalEmbedder(model="m", dimension=768),
        ],
        ids=["ollama", "openai", "local"],
    )
    def test_exposes_dimension_and_model_name(self, embedder):
        assert embedder.dimension == 768
        assert embedder.model_name == "m"


class TestOllamaEmbedderFailures:
    """Every provider failure surfaces as ModelError."""

    def test_unreachable_host_raises_model_error(self, unused_port):
        embedder = OllamaEmbedder(
            host=f"http://127.0.0.1:{unused_port}", model="any", dimension=8, timeout=5
        )

        with pytest.raises(ModelError):
            embedder.embed(["hello"])

    def test_timeout_raises_model_error(self, silent_server):
        embedder = OllamaEmbedder(host=silent_server, model="any", dimension=8, timeout=0.2)

        with pytest.raises(ModelError):
            embedder.embed(["hello"])


class TestOpenAIEmbedder:
    def test_batches_up_to_100_texts_per_request(self):
        texts = [f"text {i}" for i in range(250)]

        with FakeOpenAIEmbeddings() as server:
            embedder = OpenAIEmbedder(
                api_key="k", model="m", dimension=2, timeout=5, base_url=server.base_url
            )
            vectors = embedder.embed(texts)

        assert [len(batch) for batch in server.requests] == [100, 100, 50]
        assert vectors == [[float(len(text)), 1.0] for text in texts]

    def test_no_texts_makes_no_request(self):
        with FakeOpenAIEmbeddings() as server:
            embedder = OpenAIEmbedder(
                api_key="k", model="m", dimension=2, timeout=5, base_url=server.base_url
            )

            assert embedder.embed([]) == []

        assert server.requests == []

    def test_missing_api_key_raises_model_error(self):
        embedder = OpenAIEmbedder(api_key=None, model="m", dimension=2, timeout=5)

        with pytest.raises(ModelError):
            embedder.embed(["hello"])

    def test_unreachable_host_raises_model_error(self, unused_port):
        embedder = OpenAIEmbedder(
            api_key="k",
            model="m",
            dimension=2,
            timeout=5,
            base_url=f"http://127.0.0.1:{unused_port}/v1",
        )

        with pytest.raises(ModelError):
            embedder.embed(["hello"])

    def test_timeout_raises_model_error(self, silent_server):
        embedder = OpenAIEmbedder(
            api_key="k", model="m", dimension=2, timeout=0.2, base_url=f"{silent_server}/v1"
        )

        with pytest.raises(ModelError):
            embedder.embed(["hello"])


class TestLocalEmbedderFailures:
    def test_missing_sentence_transformers_raises_model_error(self, monkeypatch):
        # A None entry in sys.modules makes the import raise ImportError.
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        embedder = LocalEmbedder(model="all-MiniLM-L6-v2", dimension=384)

        with pytest.raises(ModelError):
            embedder.embed(["hello"])


@pytest.mark.live
class TestOllamaEmbedderContract:
    """Contract test against the Ollama at LLM_BASE_URL, using the embedding settings."""

    def test_embeds_each_text_at_configured_dimension(self):
        embedder = OllamaEmbedder(
            host=settings.LLM_BASE_URL or DEFAULT_OLLAMA_HOST,
            model=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
            timeout=120,
        )

        vectors = embedder.embed(["first text", "second text"])

        assert len(vectors) == 2
        assert all(len(vector) == settings.EMBEDDING_DIMENSION for vector in vectors)

    def test_missing_model_raises_model_error(self):
        embedder = OllamaEmbedder(
            host=settings.LLM_BASE_URL or DEFAULT_OLLAMA_HOST,
            model="cartulary-no-such-model",
            dimension=8,
            timeout=30,
        )

        with pytest.raises(ModelError):
            embedder.embed(["hello"])


@pytest.mark.live
class TestOpenAIEmbedderContract:
    """Contract test against OpenAI, using OPENAI_API_KEY."""

    def test_embeds_each_text(self):
        if not settings.OPENAI_API_KEY:
            pytest.skip("OPENAI_API_KEY not set")
        embedder = OpenAIEmbedder(
            api_key=settings.OPENAI_API_KEY,
            model="text-embedding-3-small",
            dimension=1536,
            timeout=60,
        )

        vectors = embedder.embed(["first text", "second text"])

        assert len(vectors) == 2
        assert all(len(vector) == 1536 for vector in vectors)

    def test_bad_api_key_raises_model_error(self):
        embedder = OpenAIEmbedder(
            api_key="sk-cartulary-invalid", model="text-embedding-3-small", dimension=1536, timeout=60
        )

        with pytest.raises(ModelError):
            embedder.embed(["hello"])


@pytest.mark.live
class TestLocalEmbedderContract:
    """Contract test against sentence-transformers, which must be installed."""

    def test_embeds_each_text(self):
        pytest.importorskip("sentence_transformers")
        embedder = LocalEmbedder(model="all-MiniLM-L6-v2", dimension=384)

        vectors = embedder.embed(["first text", "second text"])

        assert len(vectors) == 2
        assert all(len(vector) == 384 for vector in vectors)
        assert all(isinstance(value, float) for value in vectors[0])
