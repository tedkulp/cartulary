"""Test doubles for the model ports, and a fake HTTP endpoint for adapter tests."""
import hashlib
import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from app.providers import Message, ModelError


class ScriptedChatModel:
    """Chat model that returns queued replies and records every message list it gets.

    A queued reply that is an exception is raised instead (wrapped in ModelError
    unless it already is one). Running out of replies fails the test loudly.
    """

    def __init__(self, *replies: Union[str, Exception]) -> None:
        self._replies = list(replies)
        self.calls: List[List[Message]] = []
        self.options: List[Dict[str, Optional[float]]] = []

    def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        self.calls.append(list(messages))
        self.options.append({"temperature": temperature, "max_tokens": max_tokens})
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


class FakeJsonEndpoint:
    """A local HTTP server that answers every POST with one JSON payload and records requests.

    Use it as a context manager. `base_url` is the server's root URL.
    """

    def __init__(self, payload: Dict[str, Any], status: int = 200) -> None:
        self.requests: List[RecordedRequest] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                headers = {name.lower(): value for name, value in self.headers.items()}
                fake.requests.append(RecordedRequest(self.path, headers, body))
                encoded = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeJsonEndpoint":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()


@dataclass
class RecordedRequest:
    """One request received by a FakeJsonEndpoint."""

    path: str
    headers: Dict[str, str]  # Names lower-cased
    body: Dict[str, Any]


class ConcurrentChatModel:
    """Thread-safe chat model whose reply is computed from the messages it receives.

    Records every call and the peak number of calls in flight at once, so a test can
    assert both what the model saw and how much of it ran in parallel. The reply
    callable runs outside the lock, so it may block to hold a call open.
    """

    def __init__(self, reply: Callable[[Sequence[Message]], str]) -> None:
        self._reply = reply
        self._lock = threading.Lock()
        self.calls: List[List[Message]] = []
        self.running = 0
        self.peak_running = 0

    def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        with self._lock:
            self.calls.append(list(messages))
            self.running += 1
            self.peak_running = max(self.peak_running, self.running)
        try:
            return self._reply(messages)
        finally:
            with self._lock:
                self.running -= 1
